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
    "TETO_DE_ENTRADA",
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

#: Teto do que chega a ser inspecionado, antes de qualquer regex.
#:
#: A saída nunca passa de :data:`TAMANHO_MAXIMO`, então varrer uma mensagem de
#: um megabyte inteira é trabalho jogado fora -- e trabalho que quem manda a
#: mensagem escolhe o tamanho, já que a entrada é texto de fora. Com o corte
#: antecipado o custo fica preso a um teto, não ao tamanho da entrada.
#:
#: A folga sobre :data:`TAMANHO_MAXIMO` existe porque a redação ENCURTA o
#: texto: `password=<64 caracteres>` sai como `password=***`. Sem folga, uma
#: mensagem que hoje cabe inteira depois de redigida passaria a ser cortada.
#: Quatro vezes cobre a redação de várias credenciais longas numa linha só; uma
#: entrada que encolha mais que isso recebe a marca de corte, e é o único caso
#: em que a saída difere da versão sem teto.
TETO_DE_ENTRADA = TAMANHO_MAXIMO * 4

_SUFIXOS = "|".join(sorted(CHAVES_SENSIVEIS, key=len, reverse=True))

#: `chave=valor`, `chave: valor` e `"chave": "valor"` numa tacada. O valor para
#: no primeiro espaço, vírgula, ponto e vírgula, aspas ou fecha-chaves.
#:
#: **O prefixo da chave fica FORA do match, de propósito.** `db_password=x` dá
#: match só em `password=x`, e o `db_` continua no texto sem ser tocado -- a
#: string final é a mesma que se a expressão o tivesse capturado, porque a
#: substituição devolve `chave` inalterada e só troca o valor.
#:
#: Capturá-lo com um `[\w.-]*` antes da alternação custava caro: o motor tenta
#: a alternação de doze literais em cada posição do texto e volta atrás a cada
#: uma, então o preço subia com o tamanho da mensagem mesmo quando não havia
#: nenhum `=` nem `:` nela -- justamente o caso comum de uma mensagem de erro
#: em prosa. Medido em 2 KB: 4,4 ms com o prefixo, 0,2 ms sem.
#:
#: A aspa de fechamento do valor é opcional (`"?`) para cobrir o valor que
#: chega cortado pelo :data:`TETO_DE_ENTRADA`: sem isso, um `password="segredo`
#: partido no teto não casaria com nenhuma das alternativas e o pedaço do
#: segredo sobreviveria no log.
_ATRIBUICAO = re.compile(
    r"""(?P<chave>["']?(?:""" + _SUFIXOS + r""")["']?\s*[=:]\s*)"""
    r"""(?P<valor>"[^"]*"?|'[^']*'?|[^\s,;&"'}\]]+)""",
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

    O que passa de :data:`TETO_DE_ENTRADA` é descartado **antes** da inspeção:
    a saída caberia em :data:`TAMANHO_MAXIMO` de qualquer forma, e assim o
    custo não acompanha o tamanho de uma mensagem escolhida por quem está de
    fora. O texto cortado recebe a mesma marca de qualquer outro corte.

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

    # Antes de qualquer regex -- ver `TETO_DE_ENTRADA`. A marca fica para o
    # fim, senão o `[cortado]` entraria na conta do corte definitivo.
    cortada_na_entrada = len(texto) > TETO_DE_ENTRADA
    if cortada_na_entrada:
        texto = texto[:TETO_DE_ENTRADA]

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
        return texto[:TAMANHO_MAXIMO] + "…[cortado]"
    if cortada_na_entrada:
        # Encolheu abaixo do teto ao ser redigida, mas conteúdo se perdeu no
        # corte da entrada: quem lê o log precisa saber disso.
        return texto + "…[cortado]"
    return texto
