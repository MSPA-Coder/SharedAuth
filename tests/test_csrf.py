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


def test_isencao_de_um_app_nao_vaza_para_outro() -> None:
    # Regressão: um único CSRFProtect de módulo guarda _exempt_views na
    # própria instância, não por app -- isentar uma view no app A isentava
    # a mesma view (mesmo módulo.nome) no app B, no mesmo processo.
    app_a = Flask("app_a")
    app_a.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    csrf_a = iniciar_csrf(app_a)

    @app_a.post("/alvo")
    def alvo():
        return "ok"

    csrf_a.exempt(alvo)
    assert app_a.test_client().post("/alvo").status_code == 200

    app_b = Flask("app_b")
    app_b.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    iniciar_csrf(app_b)

    @app_b.post("/alvo")
    def alvo():  # mesmo nome de função, propositalmente
        return "ok"

    # App B nunca isentou "/alvo": continua exigindo token.
    assert app_b.test_client().post("/alvo").status_code == 400
