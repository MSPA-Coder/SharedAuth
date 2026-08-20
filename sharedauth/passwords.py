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
    """A senha não atinge :data:`MIN_PASSWORD_LENGTH`.

    É um ``ValueError`` puro, não um ``click.ClickException`` — este pacote
    não depende de Click. Um comando de CLI que chamar :func:`gerar_hash`
    diretamente precisa capturar esta exceção e relançar como
    ``click.ClickException`` (ou equivalente), senão o operador recebe um
    traceback cru em vez da mensagem de erro limpa que os apps já mostram
    hoje.
    """


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


def conferir_hash(hash_: str | None, senha: str) -> bool:
    """``False`` para hash ausente, nunca uma exceção.

    Uma conta sem senha definida ainda (importação administrativa, conta só
    de token, linha em meio a migração) tem ``hash_`` nulo ou vazio.
    ``werkzeug.security.check_password_hash`` não tem essa guarda — chamar
    direto derruba o login com 500 em vez de recusar a senha.
    """
    if not hash_:
        return False
    return check_password_hash(hash_, senha)
