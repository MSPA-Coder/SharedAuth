"""Hash e política de senha — um piso comum, uma implementação.

Werkzeug já é a biblioteca testada pela comunidade para isto; este módulo não
reimplementa hashing, só evita que cada app decida um piso mínimo diferente
por acidente (era 2 no MegaSena, 15 no ControleBancario, 8 nos outros dois,
sem nenhuma razão para a diferença).
"""

from __future__ import annotations

from werkzeug.security import check_password_hash, generate_password_hash

MIN_PASSWORD_LENGTH = 8


class SenhaMuitoCurtaError(ValueError):
    """A senha não atinge :data:`MIN_PASSWORD_LENGTH`."""


def validar_tamanho(senha: str) -> None:
    """Levanta :class:`SenhaMuitoCurtaError` se a senha for curta demais."""
    if len(senha) < MIN_PASSWORD_LENGTH:
        raise SenhaMuitoCurtaError(
            f"A senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
        )


def gerar_hash(senha: str) -> str:
    """Valida o piso e devolve o hash — nunca grava senha sem validar."""
    validar_tamanho(senha)
    return generate_password_hash(senha)


def conferir_hash(hash_: str, senha: str) -> bool:
    return check_password_hash(hash_, senha)
