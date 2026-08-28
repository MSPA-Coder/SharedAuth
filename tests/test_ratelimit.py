from __future__ import annotations

import pytest
from flask import Flask

from sharedauth.ratelimit import (
    LIMITE_LOGIN_PADRAO,
    aplicar_limite,
    iniciar_limiter,
    isentar_limite,
)


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
    # Um singleton compartilharia storage mutável; instâncias por app mantêm
    # os contadores isolados.
    app_a = _app_com_login_limitado()
    cliente_a = app_a.test_client()
    cliente_a.get("/login")
    cliente_a.get("/login")
    assert cliente_a.get("/login").status_code == 429  # A esgotou o limite

    _app_com_login_limitado()  # cria o app B, sem fazer nenhuma requisição

    assert cliente_a.get("/login").status_code == 429  # A continua esgotado


# --------------------------------------------------------------------------
# Política do consumidor (A3)
# --------------------------------------------------------------------------


def _app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    app.config["TESTING"] = True
    return app


def test_limites_padrao_do_consumidor_sao_aplicados() -> None:
    app = _app()
    iniciar_limiter(app, limites_padrao=["2 per minute"])

    @app.get("/qualquer")
    def qualquer():
        return "ok"

    cliente = app.test_client()
    assert cliente.get("/qualquer").status_code == 200
    assert cliente.get("/qualquer").status_code == 200
    assert cliente.get("/qualquer").status_code == 429


def test_sem_limites_padrao_nada_e_limitado_por_omissao() -> None:
    app = _app()
    iniciar_limiter(app)

    @app.get("/qualquer")
    def qualquer():
        return "ok"

    cliente = app.test_client()
    for _ in range(5):
        assert cliente.get("/qualquer").status_code == 200


def test_desabilitado_nao_bloqueia() -> None:
    app = _app()
    iniciar_limiter(app, limites_padrao=["1 per minute"], habilitado=False)

    @app.get("/qualquer")
    def qualquer():
        return "ok"

    cliente = app.test_client()
    assert cliente.get("/qualquer").status_code == 200
    assert cliente.get("/qualquer").status_code == 200


def test_config_do_app_vence_sobre_o_parametro() -> None:
    # Compatibilidade: quem já configurava por `app.config` não muda de
    # comportamento ao adotar os parâmetros.
    app = _app()
    app.config["RATELIMIT_ENABLED"] = False
    iniciar_limiter(app, limites_padrao=["1 per minute"], habilitado=True)

    @app.get("/qualquer")
    def qualquer():
        return "ok"

    cliente = app.test_client()
    assert cliente.get("/qualquer").status_code == 200
    assert cliente.get("/qualquer").status_code == 200


# --------------------------------------------------------------------------
# aplicar_limite / isentar_limite (A4)
# --------------------------------------------------------------------------


def test_aplicar_limite_religa_a_view_e_o_limite_vale() -> None:
    """O teste que existe por causa da regressão real, três vezes repetida.

    `limiter.limit(...)` devolve uma função nova. Se `aplicar_limite` deixar
    de reatribuir a `view_functions`, a rota volta a responder 200 para
    sempre e este teste é o que percebe.
    """
    app = _app()
    limiter = iniciar_limiter(app)

    @app.get("/login")
    def login():
        return "ok"

    aplicar_limite(app, limiter, "login", "2 per minute")

    cliente = app.test_client()
    assert cliente.get("/login").status_code == 200
    assert cliente.get("/login").status_code == 200
    assert cliente.get("/login").status_code == 429


def test_aplicar_limite_aceita_varios_endpoints() -> None:
    app = _app()
    limiter = iniciar_limiter(app)

    @app.get("/a")
    def a():
        return "ok"

    @app.get("/b")
    def b():
        return "ok"

    aplicar_limite(app, limiter, ("a", "b"), "1 per minute")

    cliente = app.test_client()
    assert cliente.get("/a").status_code == 200
    assert cliente.get("/a").status_code == 429
    # Cada endpoint tem o seu próprio contador.
    assert cliente.get("/b").status_code == 200
    assert cliente.get("/b").status_code == 429


def test_aplicar_limite_repassa_opcoes() -> None:
    app = _app()
    limiter = iniciar_limiter(app, limites_padrao=["1 per minute"])

    @app.get("/polling")
    def polling():
        return "ok"

    # `override_defaults=True` é o que faz o limite dedicado substituir o
    # global em vez de somar-se a ele.
    aplicar_limite(app, limiter, "polling", "3 per minute", override_defaults=True)

    cliente = app.test_client()
    for _ in range(3):
        assert cliente.get("/polling").status_code == 200
    assert cliente.get("/polling").status_code == 429


def test_endpoint_desconhecido_falha_alto() -> None:
    app = _app()
    limiter = iniciar_limiter(app)
    with pytest.raises(KeyError, match="web.login"):
        aplicar_limite(app, limiter, "web.login", "1 per minute")


def test_isentar_limite_tira_a_rota_do_limite_global() -> None:
    app = _app()
    limiter = iniciar_limiter(app, limites_padrao=["1 per minute"])

    @app.get("/health")
    def health():
        return "ok"

    isentar_limite(app, limiter, "health")

    cliente = app.test_client()
    for _ in range(5):
        assert cliente.get("/health").status_code == 200


def test_isentar_endpoint_desconhecido_falha_alto() -> None:
    app = _app()
    limiter = iniciar_limiter(app)
    with pytest.raises(KeyError, match="coletor.health"):
        isentar_limite(app, limiter, "coletor.health")
