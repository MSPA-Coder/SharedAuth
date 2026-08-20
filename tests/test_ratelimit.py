from __future__ import annotations

from flask import Flask

from sharedauth.ratelimit import LIMITE_LOGIN_PADRAO, iniciar_limiter


def test_padrao_e_dez_por_minuto() -> None:
    assert LIMITE_LOGIN_PADRAO == "10 per minute"


def test_limite_bloqueia_apos_o_numero_configurado() -> None:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-only-not-a-real-secret"
    app.config["TESTING"] = True
    limiter = iniciar_limiter(app)

    @app.get("/login")
    @limiter.limit("2 per minute")
    def login():
        return "ok"

    cliente = app.test_client()
    assert cliente.get("/login").status_code == 200
    assert cliente.get("/login").status_code == 200
    # A terceira, na mesma janela, estoura o limite.
    assert cliente.get("/login").status_code == 429
