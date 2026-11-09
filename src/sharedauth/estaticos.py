"""Versão na URL dos estáticos, para o navegador guardá-los por um ano.

Sem isto, o Flask serve os estáticos com ``Cache-Control: no-cache``: cada página
aberta revalida cada arquivo, e são várias idas ao servidor que só confirmam o
que o navegador já tem. Não dá para simplesmente ligar um ``max-age`` longo,
porque aí um deploy que mudasse o CSS seguiria servindo o antigo a quem já o
tivesse em cache.

A saída é o arquivo carregar a própria versão na URL: ``url_for('static', ...)``
acrescenta ``?v=<hash do conteúdo>``, e a resposta de uma URL cuja versão bate
com o arquivo servido sai com um ano de cache e ``immutable``. Mudou o conteúdo,
muda a URL, e o navegador busca o novo. Pedido sem ``v`` ou com ``v`` antigo
segue como antes -- revalidando --, para que uma página velha nunca fixe por um
ano o conteúdo novo sob um endereço antigo.

Vale para os estáticos do app e para os de todo blueprint, inclusive os desta
biblioteca. O que um arquivo referencia por caminho relativo -- ``url()`` e
``@import`` no CSS, ``import`` no JS -- não passa por ``url_for`` e continua
revalidando, o que é mais lento, mas nunca serve conteúdo antigo.

O consumidor Django não usa este módulo: o WhiteNoise já resolve isso lá.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from flask import Flask, request
from werkzeug.security import safe_join

from .ui import UM_ANO_EM_SEGUNDOS

__all__ = ["PARAMETRO_VERSAO", "instalar_versao_de_estaticos"]

PARAMETRO_VERSAO = "v"


def _eh_estatico(endpoint: str | None) -> bool:
    return endpoint is not None and (endpoint == "static" or endpoint.endswith(".static"))


def _pasta(app: Flask, endpoint: str) -> str | None:
    if endpoint == "static":
        return app.static_folder
    blueprint = app.blueprints.get(endpoint.rpartition(".")[0])
    return blueprint.static_folder if blueprint is not None else None


class _SessaoForaDoCacheLongo:
    """Interface de sessão que não toca a resposta de um estático versionado.

    O Flask acrescenta ``Vary: Cookie`` a toda resposta cuja requisição consultou
    a sessão, o que qualquer ``before_request`` faz. Num estático, isso anula o
    cache sem nenhum sinal: o cabeçalho ``Cache-Control`` continua certo, mas o
    navegador só reaproveita a cópia se o cookie for idêntico ao da visita
    anterior, e o de sessão muda a cada renovação. Volta a perguntar ao servidor
    em toda página, e nenhum teste de cabeçalho percebe.

    Tem de ser aqui, e não em ``after_request``: o Flask salva a sessão depois de
    todos eles, e o cabeçalho voltaria. Pular o salvamento também tira o
    ``Set-Cookie`` de uma resposta marcada como ``public``, que não deveria tê-lo.
    A sessão não muda ao servir um arquivo, e a página seguinte a renova.

    Delega em vez de herdar porque a interface padrão do Flask é um atributo de
    classe, compartilhado por todos os apps do processo, e o consumidor pode ter
    configurado outra.
    """

    def __init__(self, original: Any) -> None:
        self._original = original

    def __getattr__(self, nome: str) -> Any:
        return getattr(self._original, nome)

    def save_session(self, app: Flask, sessao: Any, resposta: Any) -> None:
        if _eh_estatico(request.endpoint) and resposta.cache_control.immutable:
            return
        self._original.save_session(app, sessao, resposta)


def instalar_versao_de_estaticos(app: Flask) -> None:
    """Versiona as URLs de estático e dá cache longo a quem pede a versão certa.

    Não exige mudança nos templates: basta o ``url_for`` de sempre. Um ``?v=``
    escrito à mão no template fica duplicado na URL, então retire-o ao adotar.

    Chame depois de configurar uma interface de sessão própria, se houver: ela é
    embrulhada aqui (ver :class:`_SessaoForaDoCacheLongo`).

    O hash é calculado uma vez por arquivo; a chave leva o instante e o tamanho
    para que, fora da imagem (no ``flask run`` com recarga), uma edição mude a
    versão sem reiniciar.

    Quem define ``v`` por conta própria não é sobrescrito, e é o que mantém
    :func:`sharedauth.ui.url_do_asset` funcionando como antes.
    """
    versoes: dict[tuple[str, int, int], str] = {}
    app.session_interface = _SessaoForaDoCacheLongo(app.session_interface)  # type: ignore[assignment]

    def versao(endpoint: str, arquivo: str) -> str | None:
        pasta = _pasta(app, endpoint)
        caminho = safe_join(pasta, arquivo) if pasta else None
        if caminho is None:
            return None
        try:
            estado = Path(caminho).stat()
        except OSError:
            return None
        chave = (caminho, estado.st_mtime_ns, estado.st_size)
        if chave not in versoes:
            versoes[chave] = sha256(Path(caminho).read_bytes()).hexdigest()[:12]
        return versoes[chave]

    @app.url_defaults
    def _versionar(endpoint: str, valores: dict) -> None:
        if not _eh_estatico(endpoint) or PARAMETRO_VERSAO in valores:
            return
        arquivo = valores.get("filename")
        if arquivo:
            atual = versao(endpoint, arquivo)
            if atual is not None:
                valores[PARAMETRO_VERSAO] = atual

    @app.after_request
    def _cache_longo(resposta):
        if not _eh_estatico(request.endpoint) or resposta.status_code not in (200, 304):
            return resposta
        pedida = request.args.get(PARAMETRO_VERSAO)
        arquivo = (request.view_args or {}).get("filename")
        if not pedida or not arquivo or pedida != versao(request.endpoint, arquivo):
            return resposta
        resposta.cache_control.no_cache = None
        resposta.cache_control.public = True
        resposta.cache_control.max_age = UM_ANO_EM_SEGUNDOS
        resposta.cache_control.immutable = True
        return resposta
