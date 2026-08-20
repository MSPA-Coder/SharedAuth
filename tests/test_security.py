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
    # A união das quatro políticas seria mais permissiva que qualquer uma
    # delas; o padrão tem que ser a mais fechada.
    assert "img-src 'self';" in CONTENT_SECURITY_POLICY
    assert "data:" not in CONTENT_SECURITY_POLICY


def test_csp_com_data_uri_abre_so_as_imagens() -> None:
    csp = montar_csp(imagens_data_uri=True)
    assert "img-src 'self' data:;" in csp
    assert "font-src 'self';" in csp  # o `data:` do ControleBancario era sobra
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
    # Veio do Flask-Talisman no ControleRendaVariavel. Sobreviveu à saída do
    # Talisman porque é estritamente mais restritivo que não declarar nada.
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
    # O MegaSena pendura no blueprint principal, não no app. O efeito precisa
    # alcançar rotas que não são do blueprint.
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
