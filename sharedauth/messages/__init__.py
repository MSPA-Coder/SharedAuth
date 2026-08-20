"""Mensagens de status — o mesmo `flash()` do Flask, renderização comum.

Não reimplementa nada: os três apps Flask já chamam `flask.flash()`. O que
divergia era a renderização (só uma categoria estilizada no MegaSena, erro
saindo com a cor de sucesso) e a cobertura em respostas HTMX parciais (cada
template do MegaSena reescrevia o bloco `hx-swap-oob` à mão). Este módulo dá
os dois templates prontos; o app inclui, não reescreve.

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
    nada, em vez de derrubar o app com o erro de rota duplicada que o
    registro manual (sem este guard) causaria.
    """
    if app.extensions.get(_MARCA_REGISTRO):
        return
    app.extensions[_MARCA_REGISTRO] = True
    app.register_blueprint(_blueprint)
