"""Renderização comum para mensagens de status do Flask.

O módulo fornece parciais normal e OOB para HTMX com as severidades suportadas.

Um `Blueprint` do próprio Flask entrega template e CSS -- não um
`ChoiceLoader` montado à mão nem uma rota que relê o arquivo do disco a cada
requisição: `static_folder` já serve com cache condicional (ETag/304) de
graça.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Blueprint

if TYPE_CHECKING:
    from flask import Flask

TEMPLATE_PADRAO = "sharedauth/flash_messages.html"
TEMPLATE_OOB = "sharedauth/flash_messages_oob.html"

_MARCA_REGISTRO = "sharedauth_messages_registrado"

_blueprint = Blueprint(
    "sharedauth",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/sharedauth/static",
)


def registrar_mensagens(app: Flask) -> None:
    """Torna os dois parciais e o CSS disponíveis para o app.

    Uso no template base do app:

        {% include "sharedauth/flash_messages.html" %}

    E em resposta parcial HTMX que precisa atualizar o mesmo bloco sem
    recarregar a página:

        {% include "sharedauth/flash_messages_oob.html" %}

    O CSS fica em ``/sharedauth/static/flash_messages.css`` (ou
    ``url_for("sharedauth.static", filename="flash_messages.css")``).

    Chamar duas vezes no mesmo app é seguro — a segunda chamada não faz
    nada, preservando a idempotência do registro.
    """
    # O banner usa `sharedauth_icone`. Registrado aqui tambem porque um app
    # pode incluir as mensagens sem registrar o pacote de interface -- e a
    # funcao e idempotente, entao registrar duas vezes nao custa nada.
    from ..ui import registrar_icone_jinja

    registrar_icone_jinja(app)

    if app.extensions.get(_MARCA_REGISTRO):
        return
    app.extensions[_MARCA_REGISTRO] = True
    app.register_blueprint(_blueprint)
