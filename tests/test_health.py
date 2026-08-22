from __future__ import annotations

from flask import Blueprint, Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from sharedauth.health import registrar_health


def test_responde_ok_quando_a_sonda_passa(app: Flask) -> None:
    chamadas: list[int] = []
    registrar_health(app, servico="teste", verificar=lambda: chamadas.append(1))
    resposta = app.test_client().get("/health")
    assert resposta.status_code == 200
    assert resposta.get_json() == {"servico": "teste", "status": "ok"}
    assert chamadas == [1]


def test_responde_503_quando_o_banco_esta_fora(app: Flask) -> None:
    # O ponto do módulo: "o processo está de pé" não é a pergunta certa.
    def banco_fora() -> None:
        raise RuntimeError("connection refused")

    registrar_health(app, servico="teste", verificar=banco_fora)
    resposta = app.test_client().get("/health")
    assert resposta.status_code == 503
    assert resposta.get_json() == {"servico": "teste", "status": "erro"}


def test_sem_sonda_e_so_prova_de_vida(app: Flask) -> None:
    registrar_health(app, servico="teste")
    assert app.test_client().get("/health").status_code == 200


def test_registra_em_blueprint(app: Flask) -> None:
    bp = Blueprint("principal", __name__)
    registrar_health(bp, servico="teste")
    app.register_blueprint(bp)
    assert app.test_client().get("/health").status_code == 200


def test_isencao_de_rate_limit_e_de_fato_aplicada() -> None:
    # `limiter.exempt` devolve uma função nova; descartar o retorno deixa a
    # isenção sem efeito. Sem `TESTING`, senão o Limiter se desliga sozinho.
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["3 per minute"],
        storage_uri="memory://",
    )
    registrar_health(app, servico="teste", limiter=limiter)

    cliente = app.test_client()
    codigos = [cliente.get("/health").status_code for _ in range(10)]
    assert codigos == [200] * 10


def test_sem_isencao_o_limite_global_vale() -> None:
    # Prova que o teste acima mede a isenção, e não um limiter inerte.
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["3 per minute"],
        storage_uri="memory://",
    )
    registrar_health(app, servico="teste")

    cliente = app.test_client()
    codigos = [cliente.get("/health").status_code for _ in range(10)]
    assert 429 in codigos
