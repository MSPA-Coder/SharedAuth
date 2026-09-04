"""Texto de terceiro indo para um log, sem levar junto o que não deveria.

Duas coisas acontecem quando um valor que veio de fora — um login digitado, um
parâmetro de URL, uma mensagem de erro de biblioteca — é escrito num log:

1. **credencial vaza.** Uma exceção de driver que traz a URL de conexão inteira
   põe a senha do banco no log, e log é o arquivo que menos gente trata como
   secreto: vai para stdout, para o agregador, para o anexo do chamado;
2. **a linha é forjada.** Quem controla o valor controla o que parece ser uma
   linha inteira do log, se puder pôr uma quebra ali dentro. Um login como::

       joao\\n2026-08-29 03:00:00 INFO login bem-sucedido usuario=admin

   vira duas linhas, e a segunda é indistinguível de um registro verdadeiro.
   Quem for ler o log depois de um incidente lê a mentira.

O segundo é o que o nome deste módulo chama de injeção, e é o mais fácil de
esquecer — não deixa rastro e só é descoberto quando alguém precisa do log.

Módulo de núcleo: Python puro, sem Flask e sem dependência nenhuma.
"""

from __future__ import annotations

import re

__all__ = [
    "CHAVES_SENSIVEIS",
    "MARCA_REDIGIDA",
    "TAMANHO_MAXIMO",
    "sanitizar_log",
]

#: Substitui o valor redigido. Não some com o campo: saber que havia uma senha
#: ali é informação útil para quem lê o log; saber qual senha, não.
MARCA_REDIGIDA = "***"

#: Nomes cujo valor nunca deve chegar ao log. Comparados sem diferenciar
#: maiúsculas, e casando também as formas compostas (`api_key`, `access-token`,
#: `X-Auth-Token`) porque o sufixo é o que carrega o significado.
CHAVES_SENSIVEIS: frozenset[str] = frozenset(
    {
        "senha",
        "password",
        "passwd",
        "secret",
        "token",
        "authorization",
        "api_key",
        "apikey",
        "access_key",
        "private_key",
        "credential",
        "credentials",
    }
)

#: Teto de caracteres. Um valor gigante vindo de fora não pode encher o disco
#: nem afogar as linhas vizinhas.
TAMANHO_MAXIMO = 2000

_SUFIXOS = "|".join(sorted(CHAVES_SENSIVEIS, key=len, reverse=True))

#: `chave=valor`, `chave: valor` e `"chave": "valor"` numa tacada. O `[\w.-]*`
#: antes do sufixo cobre prefixos (`db_password`, `X-Auth-Token`); o valor para
#: no primeiro espaço, vírgula, ponto e vírgula, aspas ou fecha-chaves.
_ATRIBUICAO = re.compile(
    r"""(?P<chave>["']?[\w.-]*(?:""" + _SUFIXOS + r""")["']?\s*[=:]\s*)"""
    r"""(?P<valor>"[^"]*"|'[^']*'|[^\s,;&"'}\]]+)""",
    re.IGNORECASE,
)

#: `Bearer <token>` e `Basic <credencial>` não têm `=` nem `:`, então escapam da
#: expressão acima e precisam da própria.
_ESQUEMA_HTTP = re.compile(r"\b(?P<esquema>Bearer|Basic)\s+(?P<valor>[\w.\-+/=]+)", re.IGNORECASE)

#: Senha dentro de uma URL de conexão (`postgresql://user:senha@host`), que é
#: como ela costuma aparecer numa exceção de driver.
_URL_COM_CREDENCIAL = re.compile(r"(?P<inicio>://[^:/\s]+:)(?P<valor>[^@\s]+)(?P<fim>@)")

#: Tudo que não é caractere de texto imprimível vira espaço: quebra de linha,
#: retorno de carro, tabulação vertical, avanço de página e os demais controles.
#: `\t` fica de fora de propósito -- é separador legítimo em log tabular.
_CONTROLES = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")


def sanitizar_log(mensagem: object) -> str:
    """Devolve ``mensagem`` pronta para ir a um log.

    Redige credencial reconhecível, neutraliza quebra de linha e caractere de
    controle, e corta em :data:`TAMANHO_MAXIMO`.

    Aceita qualquer objeto e o converte: quem chama costuma estar tratando
    entrada de fora, e ``None`` ou um número não deveriam obrigar a uma
    conversão no ponto de uso.

    **Use o retorno.** A função não tem efeito colateral nenhum; chamá-la e
    descartar o resultado não sanitiza coisa alguma::

        sanitizar_log(login)              # não faz nada
        logger.warning("login=%s", sanitizar_log(login))   # faz

    A redação é por reconhecimento de padrão, então é uma rede, não uma
    garantia: um segredo que apareça sem nome nenhum ao lado passa. A defesa
    primária continua sendo não pôr segredo em mensagem — ver
    :mod:`sharedauth.secrets`, cujas exceções nunca carregam o valor lido.
    """
    texto = mensagem if isinstance(mensagem, str) else str(mensagem)

    # `_ESQUEMA_HTTP` primeiro: em `Authorization: Bearer abc`, a regra de
    # atribuicao casaria `Authorization:` e redigiria apenas a palavra
    # "Bearer", deixando o token inteiro para tras.
    texto = _ESQUEMA_HTTP.sub(lambda m: f"{m.group('esquema')} {MARCA_REDIGIDA}", texto)
    texto = _ATRIBUICAO.sub(lambda m: m.group("chave") + MARCA_REDIGIDA, texto)
    texto = _URL_COM_CREDENCIAL.sub(
        lambda m: m.group("inicio") + MARCA_REDIGIDA + m.group("fim"), texto
    )
    texto = _CONTROLES.sub(" ", texto)

    if len(texto) > TAMANHO_MAXIMO:
        texto = texto[:TAMANHO_MAXIMO] + "…[cortado]"
    return texto
