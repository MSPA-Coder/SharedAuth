"""Hash e política de senha com piso mínimo compartilhado.

O módulo valida o tamanho e delega geração e conferência de hash ao Werkzeug.
Também cobre os dois momentos em que uma senha troca de dono: a senha
temporária que um administrador entrega, e a troca que o próprio dono faz
para deixar de usá-la.

**O Werkzeug é importado dentro das funções que fazem hash**, e não no topo.
A política -- piso de tamanho, alfabeto da senha temporária, as regras da
troca -- é Python puro e vale igual em qualquer framework: o consumidor Django
usa `gerar_senha_temporaria` sem ter motivo nenhum para instalar Flask,
Flask-WTF e Flask-Limiter junto. Quem faz hash é quem paga a dependência, e
paga na primeira chamada. Mesmo tratamento que `sharedauth.ui` dá aos imports
da integração Flask.

Consequência prática: `gerar_hash` e `conferir_hash` levantam `ImportError` na
chamada, e não na importação do módulo, quando o extra `[flask]` não está
instalado. É o comportamento desejado -- um app que não faz hash por aqui
nunca chega nessas funções.
"""

from __future__ import annotations

import functools
import secrets

MIN_PASSWORD_LENGTH = 10

TAMANHO_SENHA_TEMPORARIA = 12

# Sem `0`, `O`, `1`, `l` e `I`: a senha temporária existe para ser ditada por
# telefone ou copiada à mão de um bilhete. Um caractere ambíguo aqui não é
# questão de estética -- vira uma tentativa de login falhada que a pessoa não
# consegue distinguir de "o administrador errou a redefinição".
_ALFABETO_SENHA_TEMPORARIA = (
    "ABCDEFGHJKLMNPQRSTUVWXYZ"  # sem I e O
    "abcdefghijkmnopqrstuvwxyz"  # sem l
    "23456789"  # sem 0 e 1
)


class SenhaMuitoCurtaError(ValueError):
    """A senha não atinge :data:`MIN_PASSWORD_LENGTH`.

    É um ``ValueError`` puro, não um ``click.ClickException`` — este pacote
    não depende de Click. Um comando de CLI que chamar :func:`gerar_hash`
    diretamente precisa capturar esta exceção e relançar como
    ``click.ClickException`` (ou equivalente), senão o operador recebe um
    traceback cru em vez de uma mensagem adequada ao operador.
    """


class SenhaAtualIncorretaError(ValueError):
    """A senha atual informada na troca não confere com o hash guardado."""


class ConfirmacaoNaoConfereError(ValueError):
    """A senha nova e sua confirmação divergem."""


class SenhaNovaIgualAAtualError(ValueError):
    """A "nova" senha é a mesma que já estava em uso.

    Não é preciosismo: o caso que motiva esta regra é a senha temporária.
    Quem foi obrigado a trocar pode redigitar a senha que o administrador
    acabou de ditar; a marca de troca pendente se apagaria, e a senha que um
    terceiro conhece continuaria valendo — exatamente o que a obrigação
    existia para impedir.
    """


def validar_tamanho(senha: str) -> None:
    """Levanta :class:`SenhaMuitoCurtaError` se a senha for curta demais."""
    if len(senha) < MIN_PASSWORD_LENGTH:
        raise SenhaMuitoCurtaError(
            f"A senha deve ter pelo menos {MIN_PASSWORD_LENGTH} caracteres."
        )


def gerar_hash(senha: str) -> str:
    """Valida o piso e devolve o hash — nunca grava senha sem validar.

    Exige o extra ``[flask]`` (por causa do Werkzeug); ver o cabeçalho.
    """
    from werkzeug.security import generate_password_hash

    validar_tamanho(senha)
    return generate_password_hash(senha)


def conferir_hash(hash_: str | None, senha: str) -> bool:
    """``False`` para hash ausente, nunca uma exceção.

    Uma conta sem senha definida pode ter ``hash_`` nulo ou vazio.
    ``werkzeug.security.check_password_hash`` não tem essa guarda — chamar
    direto derruba o login com 500 em vez de recusar a senha.
    """
    from werkzeug.security import check_password_hash

    if not hash_:
        return False
    return check_password_hash(hash_, senha)


@functools.cache
def _hash_de_equiparacao() -> str:
    """Hash descartável, gerado com o mesmo custo de :func:`gerar_hash`."""
    from werkzeug.security import generate_password_hash

    return generate_password_hash(secrets.token_urlsafe(16))


def conferir_login(hash_: str | None, senha: str, *, ativo: bool = True) -> bool:
    """Confere a senha do login gastando o mesmo tempo em todos os caminhos.

    Com ``if usuario is None or not usuario.ativo or not conferir_hash(...)``
    o scrypt só roda para conta ativa: usuário inexistente ou inativo responde
    em milissegundos e senha errada de conta ativa em dezenas deles. A mensagem
    é a mesma, mas o tempo entrega quais logins existem e quais estão ativos.

    Aqui o hash é sempre calculado: contra ``hash_`` quando há um, e contra um
    hash descartável quando ``hash_`` é ``None``/vazio (usuário inexistente ou
    sem senha). ``ativo=False`` confere e depois recusa. Devolve ``True`` só se
    há hash, a conta está ativa e a senha confere. Hash malformado vira
    ``False``, nunca exceção.

    Chame esta função **antes** de qualquer decisão que dependa de o usuário
    existir ou estar ativo, e não depois de um curto-circuito. Exige o extra
    ``[flask]`` (Werkzeug), como :func:`conferir_hash`.
    """
    from werkzeug.security import check_password_hash

    alvo = hash_ or _hash_de_equiparacao()
    try:
        confere = check_password_hash(alvo, senha)
    except ValueError:
        confere = False
    return bool(hash_) and ativo and confere


def gerar_senha_temporaria(tamanho: int = TAMANHO_SENHA_TEMPORARIA) -> str:
    """Senha aleatória para o administrador entregar a quem perdeu a sua.

    Existe para que **o administrador nunca escolha a senha de outra pessoa**.
    Uma senha escolhida por ele é uma senha que ele conhece e que tende a se
    repetir entre contas; esta é aleatória, dita uma vez e trocada no primeiro
    acesso pelo dono.

    Sorteia com :func:`secrets.choice` — nunca ``random``, que é previsível a
    partir de saídas anteriores. Não há garantia de "ao menos um dígito" nem
    classes obrigatórias: a política destes aplicativos é só o piso de
    tamanho, e forçar classes reduziria a entropia sem nada em troca.

    O valor devolvido é a única cópia em texto claro que vai existir. Quem
    chama mostra uma vez e descarta; gravar em log, em auditoria ou em coluna
    de banco anula o objetivo.
    """
    if tamanho < MIN_PASSWORD_LENGTH:
        raise SenhaMuitoCurtaError(
            f"A senha temporária deve ter pelo menos {MIN_PASSWORD_LENGTH} "
            "caracteres."
        )
    return "".join(secrets.choice(_ALFABETO_SENHA_TEMPORARIA) for _ in range(tamanho))


def validar_troca(
    *,
    hash_atual: str | None,
    senha_atual: str,
    senha_nova: str,
    confirmacao: str,
) -> None:
    """Valida a troca de senha feita pelo próprio dono. Não grava nada.

    Só argumentos nomeados, de propósito: são quatro parâmetros de texto e
    trocar dois de lugar não daria erro de tipo nenhum — passaria a conferir a
    senha errada, em silêncio, no caminho mais sensível que este pacote tem.

    A ordem das checagens é deliberada. **A senha atual vem primeiro**: quem
    não a sabe não deve descobrir, pela mensagem de erro, nada sobre a senha
    nova que tentou colocar.

    Exige a senha atual porque a alternativa transforma uma sessão sequestrada
    em tomada de conta permanente: sem essa conferência, quem chegar a um
    navegador aberto troca a senha e passa a ser o dono.

    Levanta :class:`SenhaAtualIncorretaError`,
    :class:`ConfirmacaoNaoConfereError`, :class:`SenhaNovaIgualAAtualError`
    ou :class:`SenhaMuitoCurtaError` — todas ``ValueError``, para o consumidor
    que só quer uma mensagem poder capturar a família inteira.
    """
    if not conferir_hash(hash_atual, senha_atual):
        raise SenhaAtualIncorretaError("Senha atual inválida.")
    if senha_nova != confirmacao:
        raise ConfirmacaoNaoConfereError("A confirmação da senha não confere.")
    if senha_nova == senha_atual:
        raise SenhaNovaIgualAAtualError(
            "A nova senha deve ser diferente da senha atual."
        )
    validar_tamanho(senha_nova)
