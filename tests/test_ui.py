"""Contratos dos assets de interface e de suas integrações."""

from __future__ import annotations

import pytest
from flask import Flask

from sharedauth.ui import (
    ARQUIVO_CSS,
    ARQUIVO_JS,
    CAMINHO_ESTATICO,
    SEVERIDADES,
    TRACOS_ICONE,
    UM_ANO_EM_SEGUNDOS,
    registrar_ui,
    svg_icone,
    url_do_asset,
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
        # O estático sai em passthrough: sem fechar, o arquivo fica aberto até
        # o coletor de lixo (ResourceWarning).
        with cliente.get(f"/sharedauth/ui/{arquivo}") as resposta:
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


def test_a_versao_do_pacote_bate_com_a_do_pyproject() -> None:
    """A versão pública deve corresponder aos metadados do pacote."""
    import tomllib
    from pathlib import Path

    import sharedauth

    raiz = Path(__file__).resolve().parent.parent
    do_pyproject = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
    assert sharedauth.__version__ == do_pyproject["project"]["version"]


# ---------------------------------------------------------------------------
# Cache dos assets
# ---------------------------------------------------------------------------


def test_sem_max_age_o_comportamento_e_o_de_sempre() -> None:
    """O padrao nao muda: quem ja usa `registrar_ui(app)` nao ganha prazo novo.

    O Flask responde `no-cache` por padrao, e e o que as versoes anteriores
    entregavam. Mudar isso por conta propria prenderia o navegador de quem ja
    visitou o aplicativo num CSS antigo, sem a URL versionada para sair.
    """
    app = Flask(__name__)
    registrar_ui(app)

    with app.test_client().get(f"/sharedauth/ui/{ARQUIVO_CSS}") as resposta:
        assert resposta.status_code == 200
        assert f"max-age={UM_ANO_EM_SEGUNDOS}" not in resposta.headers.get(
            "Cache-Control", ""
        )


def test_max_age_chega_ao_cabecalho_dos_dois_arquivos() -> None:
    app = Flask(__name__)
    registrar_ui(app, max_age_segundos=UM_ANO_EM_SEGUNDOS)

    cliente = app.test_client()
    for arquivo in (ARQUIVO_CSS, ARQUIVO_JS):
        with cliente.get(f"/sharedauth/ui/{arquivo}") as resposta:
            assert resposta.status_code == 200, arquivo
            assert f"max-age={UM_ANO_EM_SEGUNDOS}" in resposta.headers["Cache-Control"], arquivo


def test_max_age_nao_vaza_para_os_estaticos_do_consumidor() -> None:
    """O prazo e do blueprint deste pacote; os estaticos do app nao sao assunto daqui."""
    app = Flask(__name__)
    registrar_ui(app, max_age_segundos=UM_ANO_EM_SEGUNDOS)

    assert app.config["SEND_FILE_MAX_AGE_DEFAULT"] is None


def test_url_do_asset_carimba_a_versao_do_pacote() -> None:
    """Sem versao na URL, prazo longo vira armadilha: ver `url_do_asset`."""
    from sharedauth import __version__

    app = Flask(__name__)
    registrar_ui(app)

    with app.test_request_context():
        url = url_do_asset(ARQUIVO_CSS)

    assert ARQUIVO_CSS in url
    assert f"v={__version__}" in url


def test_url_do_asset_esta_disponivel_no_template() -> None:
    app = Flask(__name__)
    registrar_ui(app)

    with app.test_request_context():
        renderizado = app.jinja_env.from_string(
            "{{ sharedauth_asset('" + ARQUIVO_CSS + "') }}"
        ).render()

    assert renderizado.startswith("/sharedauth/ui/")
    assert "v=" in renderizado


def test_a_url_versionada_serve_o_arquivo() -> None:
    """A query nao pode fazer o Flask deixar de encontrar o estatico."""
    app = Flask(__name__)
    registrar_ui(app, max_age_segundos=UM_ANO_EM_SEGUNDOS)

    with app.test_request_context():
        url = url_do_asset(ARQUIVO_CSS)

    with app.test_client().get(url) as resposta:
        assert resposta.status_code == 200
        assert f"max-age={UM_ANO_EM_SEGUNDOS}" in resposta.headers["Cache-Control"]
