"""Contratos dos assets de interface e de suas integrações."""

from __future__ import annotations

import re

import pytest
from flask import Flask

from sharedauth.ui import (
    ARQUIVO_CSS,
    ARQUIVO_JS,
    CAMINHO_ESTATICO,
    SEVERIDADES,
    TRACOS_ICONE,
    registrar_ui,
    svg_icone,
)


# ---------------------------------------------------------------------------
# O que o Django consome
# ---------------------------------------------------------------------------


def test_caminho_estatico_existe_e_tem_os_dois_arquivos() -> None:
    """É o que vai em `STATICFILES_DIRS`. Apontar para o vazio falha silencioso:
    o Django não reclama de diretório inexistente, só não serve nada."""
    assert CAMINHO_ESTATICO.is_dir()
    assert (CAMINHO_ESTATICO / ARQUIVO_CSS).is_file()
    assert (CAMINHO_ESTATICO / ARQUIVO_JS).is_file()


def test_o_estatico_vai_no_pacote_instalado() -> None:
    """Sem isto na `package-data`, o `pip install` traz o módulo Python e deixa
    o CSS e o JS de fora -- e o defeito só aparece na imagem, não aqui."""
    import tomllib
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    dados = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
    padroes = dados["tool"]["setuptools"]["package-data"]["sharedauth"]
    assert "ui/estatico/*.css" in padroes
    assert "ui/estatico/*.js" in padroes


# ---------------------------------------------------------------------------
# O que o Flask consome
# ---------------------------------------------------------------------------


def test_registrar_ui_serve_os_arquivos() -> None:
    app = Flask(__name__)
    app.config["TESTING"] = True
    registrar_ui(app)

    cliente = app.test_client()
    for arquivo in (ARQUIVO_CSS, ARQUIVO_JS):
        resposta = cliente.get(f"/sharedauth/ui/{arquivo}")
        assert resposta.status_code == 200, arquivo


def test_registrar_ui_duas_vezes_nao_derruba_o_app() -> None:
    """Dois módulos do pacote registram coisas no mesmo app; um app que chame
    duas vezes por engano não pode morrer com erro de blueprint duplicado."""
    app = Flask(__name__)
    registrar_ui(app)
    registrar_ui(app)


def test_convive_com_o_blueprint_de_mensagens() -> None:
    """Os blueprints precisam ter nomes distintos para coexistir."""
    from sharedauth.messages import registrar_mensagens

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    registrar_mensagens(app)
    registrar_ui(app)

    nomes = set(app.blueprints)
    assert {"sharedauth", "sharedauth_ui"} <= nomes


# ---------------------------------------------------------------------------
# O ícone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("severidade", SEVERIDADES)
def test_svg_icone_desenha_cada_severidade(severidade: str) -> None:
    marcacao = svg_icone(severidade)
    assert marcacao.startswith("<svg ")
    assert 'class="sa-icone"' in marcacao
    assert 'aria-hidden="true"' in marcacao, "ícone decorativo não deve ser lido"
    assert "currentColor" in marcacao, "a cor tem que vir da severidade em volta"
    for traco in TRACOS_ICONE[severidade]:
        assert traco in marcacao


def test_severidade_desconhecida_cai_em_info_em_vez_de_quebrar() -> None:
    """Um `flash()` com categoria própria não pode derrubar a renderização."""
    assert svg_icone("categoria-que-nao-existe") == svg_icone("info")


def test_icone_nao_usa_data_uri() -> None:
    """Com `img-src 'self'`, SVG no documento passa sem exigir `data:`."""
    for severidade in SEVERIDADES:
        assert "data:" not in svg_icone(severidade)
        assert "<img" not in svg_icone(severidade)


# ---------------------------------------------------------------------------
# Representações sincronizadas
#
# O traçado do ícone existe em Python (banner no servidor) e em JavaScript
# (modal e toast no navegador). O JS não pode importar Python, então a cópia é
# inevitável. O teste mantém as representações sincronizadas.
# ---------------------------------------------------------------------------


def _tracos_do_javascript() -> dict[str, list[str]]:
    fonte = (CAMINHO_ESTATICO / ARQUIVO_JS).read_text(encoding="utf-8")
    bloco = re.search(r"var TRACOS = \{(.*?)\n  \};", fonte, re.DOTALL)
    assert bloco, "não achei o objeto TRACOS no JS -- o teste ficou cego"

    encontrados: dict[str, list[str]] = {}
    for linha in bloco.group(1).splitlines():
        casou = re.match(r"\s*(\w+):\s*\[(.*)\],?\s*$", linha)
        if not casou:
            continue
        nome, corpo = casou.groups()
        encontrados[nome] = re.findall(r'"([^"]+)"', corpo)
    return encontrados


def test_os_tracos_do_js_e_do_python_nao_divergiram() -> None:
    do_js = _tracos_do_javascript()
    do_python = {nome: list(tracos) for nome, tracos in TRACOS_ICONE.items()}

    assert do_js == do_python, (
        "o traçado do ícone divergiu entre o JavaScript e o Python.\n"
        "O banner é renderizado no servidor e o toast no navegador; se os dois "
        "desenharem ícones diferentes, a mesma severidade muda de cara "
        "dependendo de como a mensagem chegou.\n"
        f"JS:     {do_js}\n"
        f"Python: {do_python}"
    )


def test_o_js_cobre_exatamente_as_severidades_declaradas() -> None:
    assert set(_tracos_do_javascript()) == set(SEVERIDADES)


# ---------------------------------------------------------------------------
# Regras que o CSS e o JS precisam continuar respeitando
# ---------------------------------------------------------------------------


def test_css_nao_tem_url_externa_nem_data_uri() -> None:
    """`default-src 'self'` não deixa buscar de outro host, e `img-src 'self'`
    não deixa `data:`. Um `url()` aqui viraria recurso bloqueado no navegador,
    sem erro no servidor."""
    css = (CAMINHO_ESTATICO / ARQUIVO_CSS).read_text(encoding="utf-8")
    # Ignora comentários para verificar apenas dados CSS executáveis.
    sem_comentario = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    assert "url(" not in sem_comentario
    assert "data:" not in sem_comentario


def test_css_estiliza_as_quatro_severidades() -> None:
    css = (CAMINHO_ESTATICO / ARQUIVO_CSS).read_text(encoding="utf-8")
    for severidade in SEVERIDADES:
        assert f".sa-{severidade}" in css


def test_js_nao_escreve_estilo_inline() -> None:
    """A CSP é `style-src 'self'` sem `unsafe-inline`: `setAttribute('style')`
    é bloqueado pelo navegador, e a convenção do projeto é classe estática em
    vez de mutação de estilo em runtime."""
    js = (CAMINHO_ESTATICO / ARQUIVO_JS).read_text(encoding="utf-8")
    assert 'setAttribute("style"' not in js
    assert "setAttribute('style'" not in js
    assert ".style." not in js


def test_js_prende_o_foco_e_atende_o_escape() -> None:
    """O modal deve prender e restaurar o foco para manter acessibilidade."""
    js = (CAMINHO_ESTATICO / ARQUIVO_JS).read_text(encoding="utf-8")
    assert 'aria-modal' in js
    assert '"Escape"' in js
    assert "shiftKey" in js, "sem Shift+Tab o foco só circula num sentido"
    assert "gatilho.focus()" in js, "o foco tem que voltar para quem abriu"


def test_a_versao_do_pacote_bate_com_a_do_pyproject() -> None:
    """A versão pública deve corresponder aos metadados do pacote."""
    import tomllib
    from pathlib import Path

    import sharedauth

    raiz = Path(__file__).resolve().parent.parent
    do_pyproject = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
    assert sharedauth.__version__ == do_pyproject["project"]["version"]
