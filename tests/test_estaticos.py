"""Estáticos com a versão na URL ficam um ano em cache; os demais revalidam."""

from __future__ import annotations

import os
import re
from hashlib import sha256
from pathlib import Path

import pytest
from flask import Flask, url_for

from sharedauth.estaticos import instalar_versao_de_estaticos
from sharedauth.ui import ARQUIVO_CSS, UM_ANO_EM_SEGUNDOS, registrar_ui


def _versao_de(conteudo: bytes) -> str:
    return sha256(conteudo).hexdigest()[:12]


@pytest.fixture
def pasta(tmp_path: Path) -> Path:
    (tmp_path / "app.js").write_bytes(b"console.log(1);")
    return tmp_path


@pytest.fixture
def app(pasta: Path) -> Flask:
    # `static_url_path` explícito: sem ele o Flask deriva o endereço do nome da
    # pasta, que aqui é o da pasta temporária.
    app = Flask("teste", static_folder=str(pasta), static_url_path="/static")
    registrar_ui(app)
    instalar_versao_de_estaticos(app)
    return app


def test_url_carrega_o_hash_do_conteudo(app: Flask) -> None:
    with app.test_request_context():
        url = url_for("static", filename="app.js")
    assert url == f"/static/app.js?v={_versao_de(b'console.log(1);')}"


def test_estatico_de_blueprint_tambem_e_versionado(app: Flask) -> None:
    with app.test_request_context():
        url = url_for("sharedauth_ui.static", filename=ARQUIVO_CSS)
    assert re.search(r"\?v=[0-9a-f]{12}$", url)


def test_arquivo_inexistente_fica_sem_versao(app: Flask) -> None:
    with app.test_request_context():
        assert url_for("static", filename="nao-existe.css") == "/static/nao-existe.css"


def test_caminho_para_fora_da_pasta_fica_sem_versao(app: Flask) -> None:
    with app.test_request_context():
        assert "v=" not in url_for("static", filename="../fora.css")


def test_v_explicito_nao_e_sobrescrito(app: Flask) -> None:
    """É o que mantém `url_do_asset`, com a versão do pacote, como sempre foi."""
    with app.test_request_context():
        assert url_for("static", filename="app.js", v="1.2.3").endswith("?v=1.2.3")


def test_versao_certa_ganha_cache_de_um_ano(app: Flask) -> None:
    with app.test_request_context():
        url = url_for("static", filename="app.js")
    resposta = app.test_client().get(url)
    assert resposta.status_code == 200
    cache = resposta.cache_control
    assert cache.max_age == UM_ANO_EM_SEGUNDOS
    assert cache.immutable
    assert cache.public
    assert not cache.no_cache


def test_revalidacao_com_a_versao_certa_mantem_o_prazo(app: Flask) -> None:
    """Quem ainda pergunta recebe 304 com o prazo e deixa de perguntar."""
    with app.test_request_context():
        url = url_for("static", filename="app.js")
    cliente = app.test_client()
    etag = cliente.get(url).headers["ETag"]
    resposta = cliente.get(url, headers={"If-None-Match": etag})
    assert resposta.status_code == 304
    assert resposta.cache_control.max_age == UM_ANO_EM_SEGUNDOS


@pytest.mark.parametrize("consulta", ["", "?v=000000000000"])
def test_sem_versao_ou_com_versao_antiga_continua_revalidando(
    app: Flask, consulta: str
) -> None:
    """Página de antes do deploy pede a URL antiga e recebe o conteúdo novo:
    guardá-lo por um ano sob o endereço antigo seria errado."""
    resposta = app.test_client().get(f"/static/app.js{consulta}")
    assert resposta.status_code == 200
    assert resposta.cache_control.max_age is None
    assert resposta.cache_control.no_cache


def test_conteudo_novo_muda_a_url_sem_reiniciar(app: Flask, pasta: Path) -> None:
    with app.test_request_context():
        antes = url_for("static", filename="app.js")
    arquivo = pasta / "app.js"
    arquivo.write_bytes(b"console.log(2); // mudou")
    estado = arquivo.stat()
    os.utime(arquivo, ns=(estado.st_atime_ns, estado.st_mtime_ns + 1_000_000))
    with app.test_request_context():
        depois = url_for("static", filename="app.js")
    assert antes != depois

    # A URL de antes agora revalida: bate com o nome, não com o conteúdo.
    assert app.test_client().get(antes).cache_control.max_age is None


def test_rota_que_nao_e_estatico_nao_e_tocada(app: Flask) -> None:
    @app.get("/pagina")
    def pagina() -> str:
        return "ok"

    with app.test_request_context():
        assert url_for("pagina") == "/pagina"
    resposta = app.test_client().get("/pagina?v=abc")
    assert resposta.cache_control.max_age is None
