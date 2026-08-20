from __future__ import annotations

import pytest

from sharedauth.passwords import (
    MIN_PASSWORD_LENGTH,
    SenhaMuitoCurtaError,
    conferir_hash,
    gerar_hash,
    validar_tamanho,
)


def test_piso_e_oito() -> None:
    assert MIN_PASSWORD_LENGTH == 8


def test_senha_curta_e_recusada() -> None:
    with pytest.raises(SenhaMuitoCurtaError):
        validar_tamanho("1234567")  # 7 caracteres


def test_senha_no_piso_passa() -> None:
    validar_tamanho("12345678")  # 8 caracteres, não levanta


def test_gerar_hash_recusa_senha_curta() -> None:
    with pytest.raises(SenhaMuitoCurtaError):
        gerar_hash("curta12")


def test_hash_e_verificacao_de_ponta_a_ponta() -> None:
    hash_ = gerar_hash("Admin@26")
    assert conferir_hash(hash_, "Admin@26") is True
    assert conferir_hash(hash_, "outra-senha") is False


def test_hash_nunca_e_a_senha_em_texto_puro() -> None:
    hash_ = gerar_hash("Admin@26")
    assert "Admin@26" not in hash_


def test_conferir_com_hash_none_devolve_falso_sem_levantar() -> None:
    # Conta sem senha definida ainda (importação administrativa, conta só
    # de token) -- recusar a senha, não derrubar o login com 500.
    assert conferir_hash(None, "qualquer-senha") is False


def test_conferir_com_hash_vazio_devolve_falso_sem_levantar() -> None:
    assert conferir_hash("", "qualquer-senha") is False
