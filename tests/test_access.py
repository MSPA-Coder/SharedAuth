from __future__ import annotations

import pytest
from flask import Flask

from sharedauth.access import requer_login, requer_papel, requer_troca_de_senha


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

    from sharedauth.access import requer_login, requer_papel, requer_troca_de_senha

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


# --------------------------------------------------------------------------
# requer_papel
# --------------------------------------------------------------------------


def _app_com_papel(tem_papel, **kwargs) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    app.config["TESTING"] = True

    @app.get("/admin")
    @requer_papel(tem_papel, **kwargs)
    def admin():
        return "area restrita"

    @app.get("/api/admin")
    @requer_papel(tem_papel, **kwargs)
    def api_admin():
        return {"ok": True}

    return app


def test_com_o_papel_a_view_roda() -> None:
    cliente = _app_com_papel(lambda: True).test_client()
    resposta = cliente.get("/admin")
    assert resposta.status_code == 200
    assert resposta.get_data(as_text=True) == "area restrita"


def test_sem_o_papel_responde_403_e_nao_executa_a_view() -> None:
    cliente = _app_com_papel(lambda: False).test_client()
    resposta = cliente.get("/admin")
    assert resposta.status_code == 403
    assert "area restrita" not in resposta.get_data(as_text=True)


def test_recusa_em_html_levanta_para_o_errorhandler_do_consumidor() -> None:
    """`abort`, não `return`: o app precisa poder renderizar o próprio 403.

    Devolver a resposta pronta daqui passaria por cima de um
    `errorhandler(403)` registrado pelo consumidor, entregando um 403 cru sem
    a casca visual do aplicativo.
    """
    app = _app_com_papel(lambda: False)

    @app.errorhandler(403)
    def _403(erro):
        return "pagina de erro do app", 403

    resposta = app.test_client().get("/admin")
    assert resposta.status_code == 403
    assert resposta.get_data(as_text=True) == "pagina de erro do app"


def test_recusa_nunca_redireciona_para_o_login() -> None:
    """Quem chega aqui já está autenticado; falta permissão, não sessão.

    Um 302 para o login sugeriria que entrar de novo resolveria o problema.
    """
    cliente = _app_com_papel(lambda: False).test_client()
    resposta = cliente.get("/admin")
    assert resposta.status_code == 403
    assert "Location" not in resposta.headers


def test_rota_de_api_recusa_em_json() -> None:
    cliente = _app_com_papel(lambda: False).test_client()
    resposta = cliente.get("/api/admin")
    assert resposta.status_code == 403
    assert resposta.get_json() == {"error": "Acesso restrito."}


def test_chave_de_erro_da_api_e_configuravel() -> None:
    cliente = _app_com_papel(lambda: False, chave_erro_api="erro").test_client()
    assert cliente.get("/api/admin").get_json() == {"erro": "Acesso restrito."}


def test_sem_prefixo_de_api_tudo_recusa_em_html() -> None:
    cliente = _app_com_papel(lambda: False, prefixo_api=None).test_client()
    resposta = cliente.get("/api/admin")
    assert resposta.status_code == 403
    assert resposta.get_json(silent=True) is None


def test_papel_e_consultado_a_cada_requisicao() -> None:
    # O papel pode mudar durante a sessão (alguém deixa de ser admin); a
    # decisão não pode ser congelada no momento do registro da rota.
    chamadas: list[int] = []

    def tem_papel() -> bool:
        chamadas.append(1)
        return len(chamadas) == 1

    cliente = _app_com_papel(tem_papel).test_client()
    assert cliente.get("/admin").status_code == 200
    assert cliente.get("/admin").status_code == 403


def test_preserva_nome_e_docstring_da_view() -> None:
    # `@wraps`: sem isto o Flask registraria todas as views decoradas com o
    # mesmo nome e a segunda rota falharia no registro.
    app = _app_com_papel(lambda: True)
    assert app.view_functions["admin"].__name__ == "admin"


# --- requer_troca_de_senha ------------------------------------------------


def _app_com_troca_pendente(
    *,
    autenticado: list[bool],
    pendente: list[bool],
    usar_hx_redirect: bool = False,
    isentos: frozenset[str] = frozenset({"logout", "static"}),
) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    app.config["TESTING"] = True

    @app.get("/trocar-senha")
    def trocar_senha():
        return "tela de troca"

    @app.post("/logout")
    def logout():
        return "saiu"

    @app.get("/protegida")
    def protegida():
        return "conteúdo protegido"

    @app.get("/api/dado")
    def api_dado():
        return {"ok": True}

    requer_troca_de_senha(
        app,
        endpoint_troca="trocar_senha",
        endpoints_isentos=isentos,
        esta_autenticado=lambda: autenticado[0],
        precisa_trocar=lambda: pendente[0],
        usar_hx_redirect=usar_hx_redirect,
    )
    return app


def test_sem_troca_pendente_a_rota_responde_normalmente() -> None:
    app = _app_com_troca_pendente(autenticado=[True], pendente=[False])
    assert app.test_client().get("/protegida").status_code == 200


def test_troca_pendente_desvia_qualquer_rota_para_a_tela_de_troca() -> None:
    # O ponto do contrato: não é só no login. Digitar outra URL depois do
    # desvio tem de cair aqui também.
    app = _app_com_troca_pendente(autenticado=[True], pendente=[True])
    resposta = app.test_client().get("/protegida", follow_redirects=False)
    assert resposta.status_code == 302
    assert resposta.headers["Location"] == "/trocar-senha"


def test_a_propria_tela_de_troca_nunca_entra_em_laco() -> None:
    # `endpoint_troca` é isento automaticamente -- sem isso, a tela que existe
    # para sair da situação redireciona para si mesma para sempre.
    app = _app_com_troca_pendente(autenticado=[True], pendente=[True])
    assert app.test_client().get("/trocar-senha").status_code == 200


def test_logout_isento_permite_sair_de_dentro_da_trava() -> None:
    app = _app_com_troca_pendente(autenticado=[True], pendente=[True])
    assert app.test_client().post("/logout").status_code == 200


def test_anonimo_nao_e_desviado_para_a_troca() -> None:
    # Quem não entrou não tem senha a trocar; o assunto dele é o login.
    app = _app_com_troca_pendente(autenticado=[False], pendente=[True])
    assert app.test_client().get("/protegida").status_code == 200


def test_rota_de_api_com_troca_pendente_responde_403_json() -> None:
    # 403 e não 401: a sessão vale, a identidade está estabelecida. Entrar de
    # novo não resolveria nada.
    app = _app_com_troca_pendente(autenticado=[True], pendente=[True])
    resposta = app.test_client().get("/api/dado")
    assert resposta.status_code == 403
    assert resposta.get_json() == {"error": "Troca de senha obrigatória."}


def test_requisicao_htmx_com_troca_pendente_devolve_hx_redirect() -> None:
    app = _app_com_troca_pendente(
        autenticado=[True], pendente=[True], usar_hx_redirect=True
    )
    resposta = app.test_client().get("/protegida", headers={"HX-Request": "true"})
    assert resposta.status_code == 403
    assert resposta.headers["HX-Redirect"] == "/trocar-senha"


def test_a_marca_e_consultada_a_cada_requisicao() -> None:
    # Depois da troca, o mesmo app tem de liberar sem reiniciar.
    pendente = [True]
    app = _app_com_troca_pendente(autenticado=[True], pendente=pendente)
    cliente = app.test_client()
    assert cliente.get("/protegida", follow_redirects=False).status_code == 302
    pendente[0] = False
    assert cliente.get("/protegida").status_code == 200


def test_registrar_a_trava_duas_vezes_no_mesmo_app_levanta_erro() -> None:
    app = _app_com_troca_pendente(autenticado=[True], pendente=[False])
    with pytest.raises(RuntimeError, match="uma vez só"):
        requer_troca_de_senha(
            app,
            endpoint_troca="trocar_senha",
            endpoints_isentos=frozenset(),
            esta_autenticado=lambda: True,
            precisa_trocar=lambda: True,
        )


def test_a_trava_convive_com_requer_login_na_mesma_aplicacao() -> None:
    # Os dois portões são independentes: o de login barra o anônimo, o de
    # troca barra quem entrou com senha temporária.
    app = _app_com_troca_pendente(
        autenticado=[True], pendente=[True], isentos=frozenset({"logout", "static"})
    )
    requer_login(
        app,
        endpoints_publicos=frozenset({"trocar_senha", "logout", "static"}),
        endpoint_login="trocar_senha",
        esta_autenticado=lambda: True,
    )
    resposta = app.test_client().get("/protegida", follow_redirects=False)
    assert resposta.headers["Location"] == "/trocar-senha"
