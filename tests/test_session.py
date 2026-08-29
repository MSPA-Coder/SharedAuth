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


def test_duracao_do_lembrete_aplicada_quando_informada(app: Flask) -> None:
    configurar_sessao(
        app,
        nome_cookie="teste_session",
        https_obrigatorio=False,
        duracao_lembrete_horas=12,
    )
    assert app.config["REMEMBER_COOKIE_DURATION"].total_seconds() == 12 * 3600


def test_sem_duracao_do_lembrete_a_chave_fica_ausente(app: Flask) -> None:
    """Guarda a razão de `duracao_lembrete_horas` existir.

    Omitir o parâmetro **não é neutro**: sem `REMEMBER_COOKIE_DURATION` na
    config, vale o padrão do Flask-Login, que é de 365 dias. Num app que chama
    `login_user(..., remember=True)` como comportamento padrão, isso significa
    um cookie de autenticação válido por um ano.

    O teste afirma sobre a ausência da chave, e não sobre a constante do
    Flask-Login: `sharedauth.session` só grava configuração que o Flask-Login
    lê, e não o importa — este pacote não declara Flask-Login como dependência
    nem no extra `[flask]`. Importá-lo aqui furaria essa fronteira para
    verificar um valor que pertence à outra biblioteca.
    """
    configurar_sessao(app, nome_cookie="teste_session", https_obrigatorio=False)
    assert "REMEMBER_COOKIE_DURATION" not in app.config
