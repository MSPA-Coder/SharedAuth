from __future__ import annotations

from flask import Flask

from sharedauth.session import configurar_sessao


def test_padrao_https_desligado(app: Flask) -> None:
    configurar_sessao(app, nome_cookie="teste_session", https_obrigatorio=False)
    assert app.config["SESSION_COOKIE_NAME"] == "teste_session"
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_SECURE"] is False


def test_secure_segue_https_obrigatorio(app: Flask) -> None:
    configurar_sessao(app, nome_cookie="teste_session", https_obrigatorio=True)
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["REMEMBER_COOKIE_SECURE"] is True


def test_duracao_aplicada_quando_informada(app: Flask) -> None:
    configurar_sessao(
        app, nome_cookie="teste_session", https_obrigatorio=False, duracao_horas=12
    )
    assert app.permanent_session_lifetime.total_seconds() == 12 * 3600


def test_duracao_omitida_nao_altera_padrao(app: Flask) -> None:
    padrao = app.permanent_session_lifetime
    configurar_sessao(app, nome_cookie="teste_session", https_obrigatorio=False)
    assert app.permanent_session_lifetime == padrao
