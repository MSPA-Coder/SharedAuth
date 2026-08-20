from __future__ import annotations

from flask import Flask

from sharedauth.access import requer_login


def _montar_app(*, usar_hx_redirect: bool, autenticado: list[bool]) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    app.config["TESTING"] = True

    @app.get("/login")
    def login():
        return "tela de login"

    @app.get("/protegida")
    def protegida():
        return "conteúdo protegido"

    @app.get("/api/dado")
    def api_dado():
        return {"ok": True}

    requer_login(
        app,
        endpoints_publicos=frozenset({"login", "static"}),
        endpoint_login="login",
        esta_autenticado=lambda: autenticado[0],
        usar_hx_redirect=usar_hx_redirect,
    )
    return app


def test_endpoint_publico_nao_exige_sessao() -> None:
    app = _montar_app(usar_hx_redirect=False, autenticado=[False])
    resposta = app.test_client().get("/login")
    assert resposta.status_code == 200


def test_autenticado_acessa_rota_protegida() -> None:
    app = _montar_app(usar_hx_redirect=False, autenticado=[True])
    resposta = app.test_client().get("/protegida")
    assert resposta.status_code == 200


def test_nao_autenticado_e_redirecionado_para_login() -> None:
    app = _montar_app(usar_hx_redirect=False, autenticado=[False])
    resposta = app.test_client().get("/protegida", follow_redirects=False)
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_nao_autenticado_em_rota_api_recebe_401_json() -> None:
    app = _montar_app(usar_hx_redirect=False, autenticado=[False])
    resposta = app.test_client().get("/api/dado")
    assert resposta.status_code == 401
    assert resposta.get_json() == {"erro": "Autenticação necessária."}


def test_sessao_expirada_em_requisicao_htmx_devolve_hx_redirect() -> None:
    app = _montar_app(usar_hx_redirect=True, autenticado=[False])
    resposta = app.test_client().get("/protegida", headers={"HX-Request": "true"})
    assert resposta.status_code == 401
    assert resposta.headers["HX-Redirect"].endswith("/login")


def test_sem_hx_redirect_requisicao_htmx_segue_fluxo_normal() -> None:
    # Com usar_hx_redirect=False, uma requisição HTMX para rota não-API é
    # tratada como navegação comum -- é o padrão do ControleRendaVariavel.
    app = _montar_app(usar_hx_redirect=False, autenticado=[False])
    resposta = app.test_client().get(
        "/protegida", headers={"HX-Request": "true"}, follow_redirects=False
    )
    assert resposta.status_code == 302
