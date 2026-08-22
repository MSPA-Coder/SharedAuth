"""Hash e política de senha com piso mínimo compartilhado.

O módulo valida o tamanho e delega geração e conferência de hash ao Werkzeug.
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
    traceback cru em vez de uma mensagem adequada ao operador.
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

    Uma conta sem senha definida pode ter ``hash_`` nulo ou vazio.
    ``werkzeug.security.check_password_hash`` não tem essa guarda — chamar
    direto derruba o login com 500 em vez de recusar a senha.
    """
    if not hash_:
        return False
    return check_password_hash(hash_, senha)
