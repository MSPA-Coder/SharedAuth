"""Sessão: cookies, permanência, e a amarra entre a sessão e a senha em vigor.

Não decide `SECRET_KEY` nem string de conexão: isso é bootstrap específico de
do consumidor. Este módulo só resolve as chaves de config do Flask relacionadas a cookie
de sessão.

A parte de baixo do módulo — :func:`marca_de_sessao`, :func:`marcas_conferem`,
:func:`identificador_de_sessao` e :func:`separar_identificador` — é Python
puro e não toca Flask: o consumidor que tem mecanismo de sessão próprio usa as
mesmas funções que quem usa Flask-Login.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

#: Tamanho da marca em caracteres hexadecimais. 32 = 128 bits, folgado para o
#: que ela precisa resistir (adivinhação online contra um valor que já viaja
#: num cookie assinado) e curto o bastante para não inchar o cookie.
_TAMANHO_DA_MARCA = 32

#: Separa o id do dono da marca no identificador de sessão. Não pode aparecer
#: no hexadecimal da marca, e não aparece.
_SEPARADOR = ":"


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


# ---------------------------------------------------------------------------
# Amarrar a sessão à senha em vigor
#
# Trocar a senha não derruba, por si só, as sessões abertas em outros lugares:
# tanto o cookie de sessão quanto o "lembrar-me" guardam QUEM é a pessoa, não
# QUAL senha estava valendo. Quem troca a senha porque desconfia que alguém
# entrou continua com esse alguém dentro do sistema -- e é justamente nesse
# momento que a pessoa acredita ter resolvido o problema.
#
# A saída é a mesma do Django (`update_session_auth_hash`): guardar junto da
# sessão uma marca derivada da senha guardada, e recusar a sessão cuja marca
# não corresponda mais.
# ---------------------------------------------------------------------------


def marca_de_sessao(senha_hash: str | None, *, chave_secreta: str) -> str:
    """Impressão curta da senha guardada, para amarrar a sessão a ela.

    Recebe o **hash** da senha, nunca a senha. A marca muda quando a senha
    muda, e é isso que faz uma sessão antiga parar de valer.

    HMAC com a `SECRET_KEY` do consumidor, e não um hash simples: assim a marca
    não pode ser derivada de um vazamento só do banco. Não substitui a
    assinatura do cookie — soma-se a ela.

    Truncada em :data:`_TAMANHO_DA_MARCA`: ela vai junto do id em todo cookie,
    e o que precisa resistir é adivinhação online, não análise offline.

    ``chave_secreta`` vem do consumidor porque esta biblioteca deliberadamente
    não decide segredo (ver o cabeçalho). Trocar a chave invalida as sessões,
    o que já era verdade — o cookie deixaria de conferir a assinatura de todo
    jeito.
    """
    digest = hmac.new(
        chave_secreta.encode("utf-8"),
        (senha_hash or "").encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:_TAMANHO_DA_MARCA]


def marcas_conferem(guardada: str | None, atual: str | None) -> bool:
    """Compara duas marcas em tempo constante. Ausente nunca confere.

    ``hmac.compare_digest`` e não ``==``: comparar segredo com igualdade comum
    vaza, pelo tempo, quantos caracteres iniciais coincidem.

    Sessão sem marca (de antes desta mudança, ou adulterada) devolve ``False``
    — **recusar é o lado seguro**: o custo é um login a mais, e o custo do
    contrário é a sessão que se queria derrubar continuar valendo.
    """
    if not guardada or not atual:
        return False
    return hmac.compare_digest(guardada, atual)


def identificador_de_sessao(usuario_id: object, marca: str) -> str:
    """Monta o identificador que o Flask-Login guarda no cookie.

    O Flask-Login guarda o que ``User.get_id()`` devolver, e é isso que ele
    entrega de volta ao ``user_loader``. Pendurar a marca ali é o que permite
    recusar a sessão antiga sem inventar armazenamento nenhum.
    """
    return f"{usuario_id}{_SEPARADOR}{marca}"


def separar_identificador(valor: str | None) -> tuple[str, str] | None:
    """Desfaz :func:`identificador_de_sessao`. ``None`` para formato inválido.

    Formato inválido inclui o identificador ANTIGO, de antes desta mudança, que
    era só o id. Devolver ``None`` ali é o comportamento desejado: no primeiro
    acesso depois do deploy as sessões abertas caem, uma vez só, e cada pessoa
    entra de novo.

    Corta na ÚLTIMA ocorrência do separador: a marca é hexadecimal e nunca o
    contém, então o que estiver antes é o id inteiro, mesmo que ele próprio
    tenha um.
    """
    if not valor or _SEPARADOR not in valor:
        return None
    usuario_id, _, marca = valor.rpartition(_SEPARADOR)
    if not usuario_id or not marca:
        return None
    return usuario_id, marca
