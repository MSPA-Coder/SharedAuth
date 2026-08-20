"""Configuração de sessão/cookie — a parte que os quatro apps já faziam quase
idêntica, cada um escrevendo as mesmas seis linhas de novo.

Não decide `SECRET_KEY` nem string de conexão: isso é bootstrap específico de
cada app (arquivo de segredo Docker, variável de ambiente própria) e continua
lá. Este módulo só resolve as chaves de config do Flask relacionadas a cookie
de sessão.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask


def configurar_sessao(
    app: Flask,
    *,
    nome_cookie: str,
    https_obrigatorio: bool,
    duracao_horas: float | None = None,
) -> None:
    """Aplica o padrão comum: HttpOnly, SameSite=Lax, Secure se HTTPS.

    ``https_obrigatorio`` normalmente vem da mesma flag de ambiente
    (``*_FORCE_HTTPS``) que cada app já lê para decidir redirecionamento e
    HSTS — passe o valor já resolvido, este módulo não lê ambiente sozinho.
    """
    app.config["SESSION_COOKIE_NAME"] = nome_cookie
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = https_obrigatorio

    # Flask-Login usa REMEMBER_COOKIE_* para a sessão persistente
    # ("lembrar-me"); mesmas garantias do cookie de sessão.
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
    app.config["REMEMBER_COOKIE_SECURE"] = https_obrigatorio

    if duracao_horas is not None:
        app.permanent_session_lifetime = timedelta(hours=duracao_horas)
