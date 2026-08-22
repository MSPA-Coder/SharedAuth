from __future__ import annotations

import pytest
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


def test_next_sem_query_string_nao_tem_interrogacao_sobrando() -> None:
    # request.full_path do Werkzeug sempre termina em "?", mesmo sem query
    # string -- next=/protegida%3F em vez de next=/protegida.
    app = _montar_app(usar_hx_redirect=False, autenticado=[False])
    resposta = app.test_client().get("/protegida", follow_redirects=False)
    assert resposta.headers["Location"] == "/login?next=/protegida"


def test_next_com_query_string_e_preservado() -> None:
    app = _montar_app(usar_hx_redirect=False, autenticado=[False])
    resposta = app.test_client().get(
        "/protegida?aba=historico", follow_redirects=False
    )
    assert "aba%3Dhistorico" in resposta.headers["Location"]


def test_nao_autenticado_em_rota_api_recebe_401_json() -> None:
    # A chave padrão é configurável para APIs com outra convenção.
    app = _montar_app(usar_hx_redirect=False, autenticado=[False])
    resposta = app.test_client().get("/api/dado")
    assert resposta.status_code == 401
    assert resposta.get_json() == {"error": "Autenticação necessária."}


def test_chave_do_erro_json_e_configuravel() -> None:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    app.config["TESTING"] = True

    @app.get("/api/dado")
    def api_dado():
        return {"ok": True}

    from sharedauth.access import requer_login

    requer_login(
        app,
        endpoints_publicos=frozenset({"static"}),
        endpoint_login="static",
        esta_autenticado=lambda: False,
        chave_erro_api="erro",
    )
    resposta = app.test_client().get("/api/dado")
    assert resposta.get_json() == {"erro": "Autenticação necessária."}


def test_sessao_expirada_em_requisicao_htmx_devolve_hx_redirect() -> None:
    app = _montar_app(usar_hx_redirect=True, autenticado=[False])
    resposta = app.test_client().get("/protegida", headers={"HX-Request": "true"})
    assert resposta.status_code == 401
    assert resposta.headers["HX-Redirect"].endswith("/login")


def test_sem_hx_redirect_requisicao_htmx_segue_fluxo_normal() -> None:
    # Com usar_hx_redirect=False, uma requisição HTMX para rota não-API é
    # tratada como navegação comum.
    app = _montar_app(usar_hx_redirect=False, autenticado=[False])
    resposta = app.test_client().get(
        "/protegida", headers={"HX-Request": "true"}, follow_redirects=False
    )
    assert resposta.status_code == 302


def test_registrar_duas_vezes_no_mesmo_app_levanta_erro() -> None:
    # Flask não deduplica before_request: uma segunda chamada com
    # parâmetros diferentes tornaria a primeira silenciosamente vencedora
    # para parte das rotas -- perigoso demais para passar em silêncio.
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"

    requer_login(
        app,
        endpoints_publicos=frozenset({"static"}),
        endpoint_login="static",
        esta_autenticado=lambda: False,
    )
    with pytest.raises(RuntimeError):
        requer_login(
            app,
            endpoints_publicos=frozenset({"static"}),
            endpoint_login="static",
            esta_autenticado=lambda: True,
        )
