"""Inicialização de proteção CSRF via Flask-WTF."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask_wtf.csrf import CSRFProtect

if TYPE_CHECKING:
    from flask import Flask


def iniciar_csrf(app: Flask) -> CSRFProtect:
    """Cria e inicializa uma instância própria para ``app``.

    Deliberadamente **não** é um singleton de módulo: ``CSRFProtect`` guarda
    o conjunto de views isentas (``.exempt()``) na própria instância, não por
    app. Um singleton compartilhado vazaria a isenção entre apps no mesmo
    processo; cada app recebe a sua instância.
    """
    csrf = CSRFProtect()
    csrf.init_app(app)
    return csrf
