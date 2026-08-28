"""Leitura de configuração de implantação vinda do ambiente.

Python puro: o módulo não importa Flask, Werkzeug nem SQLAlchemy, e não lê
arquivo nenhum. Ele resolve dois contratos que os consumidores reescreviam
cada um do seu jeito — interpretar um interruptor booleano e montar a URL de
conexão do PostgreSQL.

**Este módulo não trata segredo.** Senha entra em :func:`montar_url_postgres`
já resolvida pelo consumidor; a leitura do segredo em si não é
responsabilidade daqui.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

__all__ = [
    "FlagInvalidaError",
    "VALORES_FALSOS",
    "VALORES_VERDADEIROS",
    "ler_flag",
    "montar_url_postgres",
]

#: Aceitos como verdadeiro, em minúsculas e já sem espaços nas pontas.
VALORES_VERDADEIROS = frozenset({"1", "true", "yes", "on", "sim"})

#: Aceitos como falso. A string vazia entra aqui: uma variável definida como
#: vazia é a forma usual do Compose dizer "não informada".
VALORES_FALSOS = frozenset({"", "0", "false", "no", "off", "nao", "não"})


class FlagInvalidaError(ValueError):
    """A variável existe mas não é reconhecível como booleano.

    É um ``ValueError`` puro, não uma exceção de framework — este pacote não
    depende de Flask nem de Click. Quem chama decide se isso derruba a
    inicialização ou vira mensagem para o operador.
    """


def ler_flag(
    nome: str,
    *,
    padrao: bool = False,
    estrito: bool = True,
    ambiente: Mapping[str, str] | None = None,
) -> bool:
    """Lê ``nome`` do ambiente como booleano.

    ``estrito`` decide o que acontece com um valor irreconhecível, e é a razão
    de esta função existir em vez de cada aplicação ter a sua:

    - ``estrito=True`` (padrão) levanta :class:`FlagInvalidaError`. É o
      comportamento correto para interruptor que afeta segurança: um
      ``RATE_LIMIT=sim, por favor`` precisa derrubar a inicialização, não
      virar ``False`` em silêncio e desligar a proteção sem ninguém notar.
    - ``estrito=False`` devolve ``padrao``. Serve para preferência
      operacional onde um valor estranho não deve impedir o serviço de subir.

    O padrão é o estrito **de propósito**: quem precisa da tolerância pede por
    nome, e a leitura do código mostra qual dos dois está em jogo.

    Variável ausente devolve ``padrao`` nos dois modos — ausência não é erro,
    é a configuração não ter sido informada.
    """
    valores = os.environ if ambiente is None else ambiente
    bruto = valores.get(nome)
    if bruto is None:
        return padrao

    normalizado = bruto.strip().lower()
    if normalizado in VALORES_VERDADEIROS:
        return True
    if normalizado in VALORES_FALSOS:
        return False

    if estrito:
        raise FlagInvalidaError(
            f"{nome} deve ser um valor booleano reconhecível "
            f"(por exemplo: true/false, 1/0, on/off); recebido: {bruto!r}."
        )
    return padrao


def _hospedeiro_para_url(host: str) -> str:
    """Envolve literal IPv6 em colchetes; devolve o resto intacto.

    Sem isto, um ``host`` como ``::1`` produziria
    ``postgresql://u:s@::1:5432/db``, onde o primeiro ``:`` do endereço é lido
    como separador de porta e a conexão vai para outro lugar (ou falha com uma
    mensagem que não aponta para a causa). Nome de host e IPv4 não têm ``:`` e
    passam sem alteração.
    """
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def montar_url_postgres(
    *,
    usuario: str,
    senha: str,
    host: str,
    banco: str,
    porta: int | str = 5432,
    driver: str = "postgresql+psycopg",
) -> str:
    """Monta a URL de conexão com escape correto de cada componente.

    O escape **não é cosmético**. `usuario`, `senha` e `banco` passam por
    ``quote(..., safe="")``: uma senha contendo ``@`` partiria a URL no lugar
    errado e a conexão iria para um host que não é o pretendido; uma contendo
    ``/`` ou ``:`` produziria um banco ou uma porta inventados. São falhas que
    não se anunciam como erro de escape — aparecem como "não conecta" ou, pior,
    como uma mensagem de erro do driver carregando parte do segredo.

    A URL devolvida **contém a senha em texto**, porque é isso que o driver
    espera receber. Trate o retorno como segredo: não registre em log, não
    coloque em mensagem de exceção e não grave em arquivo de configuração.
    """
    from urllib.parse import quote

    if not usuario:
        raise ValueError("usuario é obrigatório para montar a URL do PostgreSQL.")
    if not host:
        raise ValueError("host é obrigatório para montar a URL do PostgreSQL.")
    if not banco:
        raise ValueError("banco é obrigatório para montar a URL do PostgreSQL.")

    try:
        numero_porta = int(porta)
    except (TypeError, ValueError) as erro:
        raise ValueError(f"porta deve ser um número; recebido: {porta!r}.") from erro
    if not 1 <= numero_porta <= 65535:
        raise ValueError(f"porta fora da faixa válida (1-65535): {numero_porta}.")

    return (
        f"{driver}://{quote(usuario, safe='')}:{quote(senha, safe='')}"
        f"@{_hospedeiro_para_url(host)}:{numero_porta}/{quote(banco, safe='')}"
    )
