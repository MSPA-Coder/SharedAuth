"""Configuração compartilhada de cookies de sessão e de permanência.

Não decide `SECRET_KEY` nem string de conexão: isso é bootstrap específico de
do consumidor. Este módulo só resolve as chaves de config do Flask relacionadas a cookie
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
    duracao_lembrete_horas: float | None = None,
) -> None:
    """Aplica o padrão comum: HttpOnly, SameSite=Lax, Secure se HTTPS.

    ``https_obrigatorio`` normalmente vem da mesma flag de ambiente
    que o consumidor usa para decidir redirecionamento e HSTS; passe o valor
    já resolvido, pois este módulo não lê ambiente sozinho.

    ``duracao_horas`` define ``permanent_session_lifetime`` — quanto tempo vale
    uma sessão marcada como permanente.

    ``duracao_lembrete_horas`` define ``REMEMBER_COOKIE_DURATION``, e **é a que
    decide quanto tempo alguém continua autenticado sem digitar a senha de
    novo**. Sem ela, o padrão do Flask-Login vale: **365 dias**. Num aplicativo
    que chama ``login_user(..., remember=True)`` — o que é o comportamento
    padrão de vários, não uma caixa que a pessoa marca —, isso significa que um
    cookie copiado de um navegador vale por um ano.

    Omitir as duas mantém os padrões do Flask e do Flask-Login, e é por isso que
    a omissão não é neutra: ela é o caminho para o ano inteiro. Passe um teto
    explícito em qualquer aplicativo com dado que você não publicaria.
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

    if duracao_lembrete_horas is not None:
        app.config["REMEMBER_COOKIE_DURATION"] = timedelta(
            hours=duracao_lembrete_horas
        )
