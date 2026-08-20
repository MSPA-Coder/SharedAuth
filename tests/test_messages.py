from __future__ import annotations

from flask import Flask, flash, render_template

from sharedauth.messages import TEMPLATE_OOB, TEMPLATE_PADRAO, registrar_mensagens


def _app_com_rotas() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    app.config["TESTING"] = True
    registrar_mensagens(app)

    @app.get("/sem-mensagem")
    def sem_mensagem():
        return render_template(TEMPLATE_PADRAO)

    @app.get("/com-mensagens")
    def com_mensagens():
        flash("Salvo com sucesso.", "success")
        flash("Algo deu errado.", "error")
        return render_template(TEMPLATE_PADRAO)

    @app.get("/oob")
    def oob():
        flash("Atualizado.", "success")
        return render_template(TEMPLATE_OOB)

    @app.get("/categoria-desconhecida")
    def categoria_desconhecida():
        flash("Mensagem qualquer.", "debug")
        return render_template(TEMPLATE_PADRAO)

    return app


def test_sem_mensagem_nao_renderiza_bloco() -> None:
    app = _app_com_rotas()
    html = app.test_client().get("/sem-mensagem").get_data(as_text=True)
    assert "sharedauth-flash-messages" not in html


def test_categorias_success_e_error_aparecem_com_classes_distintas() -> None:
    app = _app_com_rotas()
    html = app.test_client().get("/com-mensagens").get_data(as_text=True)
    assert "sharedauth-flash-success" in html
    assert "Salvo com sucesso." in html
    assert "sharedauth-flash-error" in html
    assert "Algo deu errado." in html


def test_categoria_desconhecida_cai_em_info() -> None:
    app = _app_com_rotas()
    html = app.test_client().get("/categoria-desconhecida").get_data(as_text=True)
    assert "sharedauth-flash-info" in html


def test_bloco_oob_tem_o_atributo_hx_swap_oob() -> None:
    app = _app_com_rotas()
    html = app.test_client().get("/oob").get_data(as_text=True)
    assert 'hx-swap-oob="true"' in html
    assert "sharedauth-flash-success" in html


def test_bloco_oob_e_emitido_mesmo_sem_mensagem_nova() -> None:
    # É o que permite limpar uma mensagem antiga da tela: o bloco OOB
    # sempre substitui o que já está lá, mesmo vazio.
    app = _app_com_rotas()
    app.add_url_rule(
        "/oob-vazio", view_func=lambda: render_template(TEMPLATE_OOB)
    )
    html = app.test_client().get("/oob-vazio").get_data(as_text=True)
    assert 'id="sharedauth-flash-messages"' in html
    assert 'hx-swap-oob="true"' in html


def test_css_e_servido() -> None:
    app = _app_com_rotas()
    resposta = app.test_client().get("/sharedauth/static/flash_messages.css")
    assert resposta.status_code == 200
    assert "sharedauth-flash-success" in resposta.get_data(as_text=True)
    assert resposta.content_type.startswith("text/css")


def test_css_servido_com_cache_condicional() -> None:
    # É o que um Blueprint dá de graça e uma rota lambda não dava: ETag e
    # suporte a 304, em vez de reler o arquivo do disco a cada requisição.
    app = _app_com_rotas()
    resposta = app.test_client().get("/sharedauth/static/flash_messages.css")
    assert resposta.headers.get("ETag")


def test_registrar_mensagens_duas_vezes_no_mesmo_app_nao_quebra() -> None:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    registrar_mensagens(app)
    registrar_mensagens(app)  # não deve levantar
    resposta = app.test_client().get("/sharedauth/static/flash_messages.css")
    assert resposta.status_code == 200
