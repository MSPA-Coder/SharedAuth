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


def iniciar_limiter(app: Flask) -> Limiter:
    """Cria e inicializa uma instância própria para ``app``.

    Deliberadamente **não** é um singleton de módulo: ``Limiter.init_app``
    reconstrói o *storage* compartilhado a cada chamada. Um singleton
    reaproveitado por dois apps no mesmo processo faz o segundo apagar os
    contadores do primeiro — reproduzido de fato durante a revisão desta
    biblioteca. Cada app recebe a sua própria instância.
    """
    limiter = Limiter(key_func=get_remote_address)
    limiter.init_app(app)
    return limiter
