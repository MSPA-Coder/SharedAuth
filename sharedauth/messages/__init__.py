"""Mensagens de status — o mesmo `flash()` do Flask, renderização comum.

Não reimplementa nada: os três apps Flask já chamam `flask.flash()`. O que
divergia era a renderização (só uma categoria estilizada no MegaSena, erro
saindo com a cor de sucesso) e a cobertura em respostas HTMX parciais (cada
template do MegaSena reescrevia o bloco `hx-swap-oob` à mão). Este módulo dá
os dois templates prontos; o app inclui, não reescreve.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import jinja2

if TYPE_CHECKING:
    from flask import Flask

_DIR = Path(__file__).resolve().parent

TEMPLATE_PADRAO = "sharedauth/flash_messages.html"
TEMPLATE_OOB = "sharedauth/flash_messages_oob.html"


def registrar_mensagens(app: Flask) -> None:
    """Torna os dois parciais e o CSS carregáveis pelo app que os inclui.

    Uso no template base do app:

        {% include "sharedauth/flash_messages.html" %}

    E em resposta parcial HTMX que precisa atualizar o mesmo bloco sem
    recarregar a página:

        {% include "sharedauth/flash_messages_oob.html" %}

    O prefixo ``sharedauth/`` isola os templates do pacote dos do app — um
    ``ChoiceLoader`` com ``PrefixLoader`` por baixo, o jeito padrão de uma
    extensão Flask trazer templates próprios sem colidir com os do app.
    """
    pacote_loader = jinja2.PrefixLoader(
        {"sharedauth": jinja2.FileSystemLoader(str(_DIR / "templates"))}
    )
    app.jinja_loader = jinja2.ChoiceLoader([app.jinja_loader, pacote_loader])  # type: ignore[list-item]

    app.add_url_rule(
        "/sharedauth/flash-messages.css",
        endpoint="sharedauth.flash_messages_css",
        view_func=lambda: (
            (_DIR / "static" / "flash_messages.css").read_text(encoding="utf-8"),
            200,
            {"Content-Type": "text/css; charset=utf-8"},
        ),
    )
