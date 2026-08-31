from __future__ import annotations

import pytest
from flask import Flask

from sharedauth.session import (
    configurar_sessao,
    identificador_de_sessao,
    marca_de_sessao,
    marcas_conferem,
    separar_identificador,
)


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


# --- amarra entre a sessao e a senha em vigor -----------------------------


CHAVE = "chave-de-teste-nao-usada-em-execucao-real"


def test_a_marca_muda_quando_a_senha_muda() -> None:
    # E o ponto inteiro do contrato: e essa mudanca que faz a sessao antiga
    # parar de valer.
    antes = marca_de_sessao("hash-antigo", chave_secreta=CHAVE)
    depois = marca_de_sessao("hash-novo", chave_secreta=CHAVE)

    assert antes != depois


def test_a_marca_e_estavel_para_a_mesma_senha() -> None:
    # Se variasse, a pessoa seria deslogada a cada requisicao.
    assert marca_de_sessao("hash", chave_secreta=CHAVE) == marca_de_sessao(
        "hash", chave_secreta=CHAVE
    )


def test_a_marca_depende_da_chave_secreta() -> None:
    # HMAC, e nao hash simples: a marca nao pode ser derivada de um vazamento
    # so do banco.
    assert marca_de_sessao("hash", chave_secreta=CHAVE) != marca_de_sessao(
        "hash", chave_secreta="outra-chave"
    )


def test_a_marca_nao_contem_o_hash_da_senha() -> None:
    assert "hash-secreto" not in marca_de_sessao("hash-secreto", chave_secreta=CHAVE)


def test_a_marca_tem_tamanho_fixo_e_hexadecimal() -> None:
    # Vai junto do id em todo cookie; tamanho previsivel importa.
    marca = marca_de_sessao("hash", chave_secreta=CHAVE)

    assert len(marca) == 32
    assert all(c in "0123456789abcdef" for c in marca)


def test_hash_ausente_ainda_produz_marca() -> None:
    # Conta sem senha definida nao pode derrubar o carregamento com excecao.
    assert marca_de_sessao(None, chave_secreta=CHAVE)


def test_marcas_iguais_conferem() -> None:
    marca = marca_de_sessao("hash", chave_secreta=CHAVE)

    assert marcas_conferem(marca, marca) is True


def test_marcas_diferentes_nao_conferem() -> None:
    assert (
        marcas_conferem(
            marca_de_sessao("antigo", chave_secreta=CHAVE),
            marca_de_sessao("novo", chave_secreta=CHAVE),
        )
        is False
    )


@pytest.mark.parametrize("ausente", [None, ""])
def test_marca_ausente_nunca_confere(ausente) -> None:
    # Sessao de antes desta mudanca, ou adulterada. Recusar e o lado seguro: o
    # custo e um login a mais.
    marca = marca_de_sessao("hash", chave_secreta=CHAVE)

    assert marcas_conferem(ausente, marca) is False
    assert marcas_conferem(marca, ausente) is False


def test_identificador_vai_e_volta() -> None:
    marca = marca_de_sessao("hash", chave_secreta=CHAVE)

    assert separar_identificador(identificador_de_sessao(7, marca)) == ("7", marca)


@pytest.mark.parametrize("invalido", [None, "", "7", "sem-separador", ":", "7:", ":m"])
def test_identificador_invalido_devolve_none(invalido) -> None:
    # "7" é o formato ANTIGO, de antes desta mudança: recusá-lo é o que derruba
    # as sessões abertas uma vez só, no primeiro acesso depois do deploy.
    assert separar_identificador(invalido) is None


def test_id_que_contenha_o_separador_ainda_volta_inteiro() -> None:
    # Corta na ÚLTIMA ocorrência: a marca é hexadecimal e nunca contém ":".
    marca = marca_de_sessao("hash", chave_secreta=CHAVE)

    assert separar_identificador(identificador_de_sessao("a:b", marca)) == ("a:b", marca)


def test_o_ciclo_completo_recusa_a_sessao_de_antes_da_troca() -> None:
    # O caso de uso inteiro, sem framework nenhum: alguém entrou com a senha
    # antiga, o dono trocou a senha, e a sessão daquele alguém tem de cair.
    guardado = identificador_de_sessao(7, marca_de_sessao("hash-antigo", chave_secreta=CHAVE))

    partes = separar_identificador(guardado)
    assert partes is not None
    _, marca_guardada = partes

    assert marcas_conferem(
        marca_guardada, marca_de_sessao("hash-antigo", chave_secreta=CHAVE)
    ) is True
    assert marcas_conferem(
        marca_guardada, marca_de_sessao("hash-novo", chave_secreta=CHAVE)
    ) is False
