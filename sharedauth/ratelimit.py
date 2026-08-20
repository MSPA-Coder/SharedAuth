"""Limite de tentativas de login — Flask-Limiter com um padrão comum.

Os três apps Flask já usavam Flask-Limiter, cada um com um número diferente
(5/min, 10/min, um terceiro sem registro claro) sem nenhum deles ter pensado
no valor do outro. Não é biblioteca nova — é o mesmo Flask-Limiter, iniciado
uma vez, com um padrão documentado em vez de reinventado.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

if TYPE_CHECKING:
    from flask import Flask

LIMITE_LOGIN_PADRAO = "10 per minute"

limiter = Limiter(key_func=get_remote_address)


def iniciar_limiter(app: Flask) -> Limiter:
    limiter.init_app(app)
    return limiter
