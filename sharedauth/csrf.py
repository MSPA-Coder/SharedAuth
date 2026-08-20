"""CSRF via Flask-WTF — um único ponto de inicialização.

Existe porque um dos quatro apps (ConfortoTermico) escreveu proteção CSRF
própria (HMAC comparado à mão) em vez de usar a biblioteca que os outros dois
irmãos Flask já usavam pronta. Este módulo não substitui Flask-WTF por nada
novo — só garante que iniciar CSRF vire uma chamada, não uma decisão de novo
a cada app.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask_wtf.csrf import CSRFProtect

if TYPE_CHECKING:
    from flask import Flask


def iniciar_csrf(app: Flask) -> CSRFProtect:
    """Cria e inicializa uma instância própria para ``app``.

    Deliberadamente **não** é um singleton de módulo: ``CSRFProtect`` guarda
    o conjunto de views isentas (``.exempt()``) na própria instância, não por
    app. Um singleton compartilhado vazaria a isenção de um app para
    qualquer outro que rode no mesmo processo (dois apps Flask no mesmo
    processo de teste, por exemplo) — cada app recebe a sua.
    """
    csrf = CSRFProtect()
    csrf.init_app(app)
    return csrf
