"""Leitura de segredo concedido por arquivo, fechada por padrão.

Python puro: não importa Flask, Werkzeug nem driver de banco. É o contrato que
os quatro aplicativos consumidores reescreviam cada um do seu jeito — dois
deles, inclusive, num arquivo com o mesmo nome (`secret_files.py`) e ainda
assim divergentes.

**Nenhuma função daqui coloca o conteúdo do segredo numa mensagem de erro, num
log ou no texto de uma exceção.** As mensagens nomeiam a variável e o que
fazer; nunca o valor. Isso é uma exigência do módulo, não um detalhe: uma
exceção com o segredo dentro viaja para o log de erro, para o terminal de quem
implanta e, num app com traceback ligado, para a resposta HTTP.

A convenção é a do Docker Compose: a variável ``NOME_FILE`` guarda o *caminho*
de um arquivo, e o arquivo guarda o valor. A variável ``NOME`` com o valor
direto é fallback opcional, para execução manual fora do Compose.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

__all__ = [
    "DIRETORIO_SECRETS_COMPOSE",
    "SegredoInvalidoError",
    "ler_arquivo_de_segredo",
    "resolver_segredo",
]

#: Onde o Docker Compose monta os segredos dentro do contêiner.
DIRETORIO_SECRETS_COMPOSE = Path("/run/secrets")


class SegredoInvalidoError(RuntimeError):
    """O segredo não pôde ser obtido de forma confiável.

    ``RuntimeError`` — e não ``ValueError`` — porque em todos os consumidores
    esta falha acontece no bootstrap e o desfecho correto é a aplicação não
    subir. O tipo já é o que o código de inicialização deles usa para isso.
    """


def ler_arquivo_de_segredo(
    nome: str,
    caminho: str | Path,
    *,
    caminho_esperado: Path | None = None,
) -> str:
    """Lê o valor de ``caminho``, recusando arquivo ausente, ilegível ou vazio.

    ``caminho_esperado`` fecha o caminho num alvo único e é a forma **mais
    segura** de usar esta função. Sem ele, a variável ``NOME_FILE`` deixa de
    ser configuração de implantação e vira um seletor arbitrário de arquivo:
    quem controlar o ambiente do processo aponta para qualquer arquivo legível
    e o conteúdo entra na aplicação como se fosse o segredo. Com ele, o
    caminho informado precisa resolver exatamente para o alvo declarado.

    A comparação é feita sobre os caminhos **resolvidos** dos dois lados, então
    um symlink ou um ``..`` no meio não contorna a checagem.

    O valor devolvido tem espaços e quebras de linha das pontas removidos: um
    editor que acrescenta ``\\n`` no fim do arquivo não pode mudar o segredo.
    """
    if caminho_esperado is not None:
        alvo = Path(caminho_esperado).resolve(strict=False)
        try:
            informado = Path(caminho).resolve(strict=True)
        except OSError as erro:
            raise SegredoInvalidoError(
                f"Não foi possível ler o segredo indicado por {nome}."
            ) from erro
        if informado != alvo or not informado.is_file():
            raise SegredoInvalidoError(f"{nome} deve apontar para {alvo}.")
        origem = informado
    else:
        origem = Path(caminho)

    try:
        valor = origem.read_text(encoding="utf-8").strip()
    except OSError as erro:
        # A exceção original carrega o caminho, não o conteúdo -- encadear com
        # `from` é seguro e preserva a causa para quem depura.
        raise SegredoInvalidoError(
            f"Não foi possível ler o segredo indicado por {nome}."
        ) from erro

    if not valor:
        raise SegredoInvalidoError(f"O arquivo indicado por {nome} está vazio.")
    return valor


def resolver_segredo(
    nome: str,
    *,
    ambiente: Mapping[str, str] | None = None,
    aceitar_variavel: bool = True,
    caminho_esperado: Path | None = None,
    obrigatorio: bool = False,
) -> str | None:
    """Resolve ``NOME_FILE`` (o caminho) antes de ``NOME`` (o valor direto).

    A precedência não é arbitrária: quando as duas existem, a concedida por
    arquivo é a do Compose e a direta é sobra de execução manual. Deixar a
    variável direta ganhar faria uma sobra no ambiente silenciosamente
    substituir o segredo operacional.

    ``aceitar_variavel=False`` recusa a forma direta por completo — é o
    contrato de quem só admite segredo montado como arquivo.

    ``obrigatorio=True`` levanta :class:`SegredoInvalidoError` quando nada foi
    configurado, em vez de devolver ``None``. Use nos segredos sem os quais a
    aplicação não pode subir: falhar aqui é melhor que subir com um fallback
    gerado, que mascara a ausência da configuração e invalida toda sessão a
    cada reinício.

    ``NOME_FILE`` definida mas vazia é **erro**, não ausência: alguém quis
    conceder o segredo por arquivo e a concessão está quebrada.
    """
    valores = ambiente
    if valores is None:
        import os

        valores = os.environ

    caminho = valores.get(f"{nome}_FILE")
    if caminho is not None:
        if not caminho.strip():
            raise SegredoInvalidoError(f"{nome}_FILE não pode estar vazio.")
        return ler_arquivo_de_segredo(
            f"{nome}_FILE", caminho.strip(), caminho_esperado=caminho_esperado
        )

    if aceitar_variavel:
        direto = valores.get(nome)
        if direto:
            return direto

    if obrigatorio:
        se_aceita = f" ou {nome} com o valor" if aceitar_variavel else ""
        raise SegredoInvalidoError(
            f"{nome} é obrigatório e não foi configurado. "
            f"Defina {nome}_FILE apontando para o arquivo do segredo{se_aceita}."
        )
    return None
