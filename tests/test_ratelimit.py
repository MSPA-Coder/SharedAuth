from __future__ import annotations

from flask import Flask

from sharedauth.ratelimit import LIMITE_LOGIN_PADRAO, iniciar_limiter


def test_padrao_e_dez_por_minuto() -> None:
    assert LIMITE_LOGIN_PADRAO == "10 per minute"


def _app_com_login_limitado(limite: str = "2 per minute") -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    app.config["TESTING"] = True
    limiter = iniciar_limiter(app)

    @app.get("/login")
    @limiter.limit(limite)
    def login():
        return "ok"

    return app


def test_limite_bloqueia_apos_o_numero_configurado() -> None:
    app = _app_com_login_limitado()
    cliente = app.test_client()
    assert cliente.get("/login").status_code == 200
    assert cliente.get("/login").status_code == 200
    # A terceira, na mesma janela, estoura o limite.
    assert cliente.get("/login").status_code == 429


def test_criar_um_segundo_app_nao_reseta_o_limite_do_primeiro() -> None:
    # Regressão: init_app reconstruía o storage de um singleton de módulo
    # compartilhado -- criar o app B apagava os contadores do app A, sem
    # nenhuma requisição contra B. Reproduzido de fato antes desta correção.
    app_a = _app_com_login_limitado()
    cliente_a = app_a.test_client()
    cliente_a.get("/login")
    cliente_a.get("/login")
    assert cliente_a.get("/login").status_code == 429  # A esgotou o limite

    _app_com_login_limitado()  # cria o app B, sem fazer nenhuma requisição

    assert cliente_a.get("/login").status_code == 429  # A continua esgotado
