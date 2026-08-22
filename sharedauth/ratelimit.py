"""Limite de tentativas de login com Flask-Limiter e política padrão."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

if TYPE_CHECKING:
    from flask import Flask

LIMITE_LOGIN_PADRAO = "10 per minute"


def iniciar_limiter(app: Flask) -> Limiter:
    """Cria e inicializa uma instância própria para ``app``.

    Deliberadamente **não** é um singleton de módulo: ``Limiter.init_app``
    reconstrói o *storage* compartilhado a cada chamada. Reaproveitar um
    singleton entre apps no mesmo processo pode apagar contadores existentes.
    Cada app recebe a sua própria instância.
    """
    limiter = Limiter(key_func=get_remote_address)
    limiter.init_app(app)
    return limiter
