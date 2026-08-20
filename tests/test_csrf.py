from __future__ import annotations

from flask import Flask

from sharedauth.csrf import iniciar_csrf


def _app_com_rota_post() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    app.config["TESTING"] = True
    iniciar_csrf(app)

    @app.post("/alvo")
    def alvo():
        return "ok"

    return app


def test_post_sem_token_e_recusado() -> None:
    app = _app_com_rota_post()
    cliente = app.test_client()
    resposta = cliente.post("/alvo")
    assert resposta.status_code == 400


def test_get_nao_exige_token() -> None:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    iniciar_csrf(app)

    @app.get("/alvo")
    def alvo():
        return "ok"

    resposta = app.test_client().get("/alvo")
    assert resposta.status_code == 200
