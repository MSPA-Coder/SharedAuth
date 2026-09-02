from __future__ import annotations

import pytest
from flask import Blueprint, Flask

from sharedauth.security import (
    CONTENT_SECURITY_POLICY,
    SECURITY_HEADERS,
    montar_csp,
    registrar_cabecalhos,
)


def _cabecalhos(app: Flask) -> dict[str, str]:
    @app.get("/")
    def raiz() -> str:
        return "ok"

    return dict(app.test_client().get("/").headers)


def test_csp_padrao_nao_permite_imagem_data_uri() -> None:
    # O padrão deve permanecer fechado; exceções são explícitas.
    assert "img-src 'self';" in CONTENT_SECURITY_POLICY
    assert "data:" not in CONTENT_SECURITY_POLICY


def test_csp_com_data_uri_abre_so_as_imagens() -> None:
    csp = montar_csp(imagens_data_uri=True)
    assert "img-src 'self' data:;" in csp
    assert "font-src 'self';" in csp
    assert csp.count("data:") == 1


@pytest.mark.parametrize(
    "diretiva",
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "font-src 'self'",
        "connect-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
    ],
)
def test_politica_fecha_todas_as_diretivas(diretiva: str) -> None:
    assert diretiva in CONTENT_SECURITY_POLICY


def test_nenhum_unsafe_inline_em_nenhuma_variante() -> None:
    for csp in (montar_csp(), montar_csp(imagens_data_uri=True)):
        assert "unsafe-inline" not in csp
        assert "unsafe-eval" not in csp


def test_permissions_policy_traz_browsing_topics(app: Flask) -> None:
    # A diretiva é mais restritiva que não declarar política para Topics API.
    registrar_cabecalhos(app)
    politica = _cabecalhos(app)["Permissions-Policy"]
    for diretiva in ("camera=()", "microphone=()", "geolocation=()", "browsing-topics=()"):
        assert diretiva in politica


def test_registra_todos_os_cabecalhos_no_app(app: Flask) -> None:
    registrar_cabecalhos(app)
    resposta = _cabecalhos(app)
    for cabecalho, valor in SECURITY_HEADERS.items():
        assert resposta[cabecalho] == valor
    assert resposta["Content-Security-Policy"] == CONTENT_SECURITY_POLICY


def test_registra_em_blueprint_valendo_para_o_app_inteiro(app: Flask) -> None:
    # O registro em blueprint precisa alcançar rotas fora dele.
    bp = Blueprint("principal", __name__)
    registrar_cabecalhos(bp, imagens_data_uri=True)
    app.register_blueprint(bp)
    resposta = _cabecalhos(app)
    assert resposta["X-Frame-Options"] == "DENY"
    assert "img-src 'self' data:" in resposta["Content-Security-Policy"]


def test_valor_ja_definido_pelo_app_vence(app: Flask) -> None:
    registrar_cabecalhos(app)

    @app.get("/proprio")
    def proprio():
        return "ok", 200, {"Content-Security-Policy": "default-src 'none'"}

    resposta = app.test_client().get("/proprio")
    assert resposta.headers["Content-Security-Policy"] == "default-src 'none'"
    # e o resto do conjunto continua aplicado
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"

# ---------------------------------------------------------------------------
# Vary: HX-Request
# ---------------------------------------------------------------------------


def _app_com_rotas() -> Flask:
    app = Flask(__name__)
    registrar_cabecalhos(app)

    @app.get("/")
    def tela() -> str:
        return "<p>ok</p>"

    @app.get("/dados.json")
    def dados():
        return {"ok": True}

    @app.get("/varia-por-idioma")
    def por_idioma():
        resposta = app.make_response("<p>ok</p>")
        resposta.vary.add("Accept-Language")
        return resposta

    return app


def test_resposta_html_declara_que_varia_por_hx_request() -> None:
    """Tela e fragmento compartilham a URL; o cache precisa saber disso.

    Sem `Vary`, um cache no caminho pode guardar o fragmento e servi-lo a
    requisicao seguinte como se fosse o documento inteiro -- a tela aparece sem
    casca. Sintoma intermitente, que some ao recarregar.
    """
    resposta = _app_com_rotas().test_client().get("/")

    assert "HX-Request" in resposta.headers.get("Vary", "")


def test_resposta_nao_html_nao_recebe_vary() -> None:
    """Acrescentar `Vary` a um JSON faria o cache guardar duas copias iguais."""
    resposta = _app_com_rotas().test_client().get("/dados.json")

    assert "HX-Request" not in resposta.headers.get("Vary", "")


def test_vary_preexistente_e_preservado() -> None:
    """Uma rota que ja varia por outro cabecalho nao pode perde-lo."""
    resposta = _app_com_rotas().test_client().get("/varia-por-idioma")

    vary = resposta.headers.get("Vary", "")
    assert "Accept-Language" in vary
    assert "HX-Request" in vary


# ---------------------------------------------------------------------------
# Strict-Transport-Security (SA-01)
# ---------------------------------------------------------------------------


def test_hsts_ausente_por_padrao(app: Flask) -> None:
    registrar_cabecalhos(app)
    assert "Strict-Transport-Security" not in _cabecalhos(app)


def test_hsts_publicado_quando_pedido(app: Flask) -> None:
    registrar_cabecalhos(app, hsts_segundos=15552000)
    valor = _cabecalhos(app)["Strict-Transport-Security"]
    assert "max-age=15552000" in valor
    assert "includeSubDomains" in valor


def test_hsts_nao_publica_preload() -> None:
    app = Flask(__name__)
    registrar_cabecalhos(app, hsts_segundos=15552000)
    assert "preload" not in _cabecalhos(app)["Strict-Transport-Security"]


def test_hsts_respeita_valor_ja_definido_pelo_app() -> None:
    app = Flask(__name__)
    registrar_cabecalhos(app, hsts_segundos=15552000)

    @app.get("/proprio")
    def proprio():
        return "ok", 200, {"Strict-Transport-Security": "max-age=1"}

    resposta = app.test_client().get("/proprio")
    assert resposta.headers["Strict-Transport-Security"] == "max-age=1"
