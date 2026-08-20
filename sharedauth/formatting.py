"""Números e dinheiro no padrão brasileiro — a mesma função, escrita três vezes.

O ControleBancario e o ControleRendaVariavel tinham a mesma rotina copiada
caractere por caractere, inclusive o truque de usar ``\\x00`` como marcador
temporário para trocar ponto e vírgula de lugar sem passar duas vezes pelo
mesmo caractere. O MegaSena tinha uma terceira variante, mais pobre, que nem
tratava centavos. Nenhuma das três estava errada; elas simplesmente foram
escritas em momentos diferentes, sem nunca terem sido comparadas.

**O que este módulo não faz:** decidir sozinho como cada tela mostra ausência
de valor. As três cópias divergiam nisso de verdade — o ControleBancario
esconde zero para não encher de "R$ 0,00" uma tabela que já é larga, o
ControleRendaVariavel mostra "-" quando não há valor, o MegaSena deixa em
branco. Essas escolhas são de apresentação e continuam com cada app, mas
agora explícitas no ponto da chamada (``ausente=``, ``ocultar_zero=``) em vez
de embutidas em três implementações diferentes da mesma conta.

**Python puro, sem dependência nenhuma** — é o que permite o ControleBancario
(Django) usar a mesma conta que os três apps Flask.
"""

from __future__ import annotations

from decimal import Decimal

Numerico = Decimal | float | int

#: O que mostrar quando não há valor. "-" ocupa a célula e diz "não há dado
#: aqui"; a string vazia deixa a célula muda, o que numa tabela larga vira
#: dúvida sobre se o valor é zero ou se faltou carregar.
AUSENTE = "-"


def _para_decimal(valor: Numerico) -> Decimal:
    """``float`` vira ``Decimal`` pela representação decimal, não binária.

    ``Decimal(0.1)`` guarda o erro do binário
    (``0.1000000000000000055511151231257827``); ``Decimal(str(0.1))`` guarda
    ``0.1``. Como o destino é sempre texto para uma tela, a segunda forma é a
    correta.
    """
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def numero(
    valor: Numerico | None,
    *,
    casas: int = 2,
    ausente: str = AUSENTE,
    ocultar_zero: bool = False,
    remover_decimal_zero: bool = False,
) -> str:
    """Milhar com ponto, decimal com vírgula.

    ``remover_decimal_zero`` omite a parte decimal quando ela é inteiramente
    zero — é o que as telas de Ações e Opções do ControleRendaVariavel usam:
    um ",00" repetido em cada coluna de dinheiro só consome largura numa
    tabela que já é larga demais. As telas onde o alinhamento das casas
    decimais importa mais que a largura continuam sem ele.
    """
    if valor is None:
        return ausente
    quantia = _para_decimal(valor)
    if ocultar_zero and quantia == 0:
        return ""
    if remover_decimal_zero and quantia == quantia.to_integral_value():
        casas = 0
    # `\x00` como marcador: trocar "," por "." e depois "." por "," passaria
    # duas vezes pelo mesmo caractere e devolveria tudo com vírgula.
    formatado = f"{quantia:,.{casas}f}"
    return formatado.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def inteiro(valor: int | None, *, ausente: str = AUSENTE) -> str:
    """Inteiro com separador de milhar, sem parte decimal."""
    return numero(valor, casas=0, ausente=ausente)


def moeda(
    valor: Numerico | None,
    *,
    casas: int = 2,
    ausente: str = AUSENTE,
    ocultar_zero: bool = False,
    remover_decimal_zero: bool = False,
    simbolo: str = "R$",
) -> str:
    """``R$ 1.234,56``. ``simbolo`` cobre as telas multimoeda do RendaVariável."""
    texto = numero(
        valor,
        casas=casas,
        ausente=ausente,
        ocultar_zero=ocultar_zero,
        remover_decimal_zero=remover_decimal_zero,
    )
    if texto in (ausente, ""):
        return texto
    return f"{simbolo} {texto}"


def moeda_com_sinal(
    valor: Numerico | None,
    *,
    casas: int = 2,
    ausente: str = AUSENTE,
    ocultar_zero: bool = True,
    simbolo: str = "R$",
) -> str:
    """``+ R$ 10,00`` / ``- R$ 10,00`` — o sinal separado do valor por espaço.

    Formato do ControleBancario, onde a coluna de movimento precisa que o
    sinal seja legível de relance. ``ocultar_zero`` é ``True`` por padrão aqui
    (e não no resto do módulo) porque um movimento de zero não é movimento.
    """
    if valor is None:
        return ausente
    quantia = _para_decimal(valor)
    if ocultar_zero and quantia == 0:
        return ""
    sinal = "+" if quantia > 0 else "-"
    texto = moeda(abs(quantia), casas=casas, ausente=ausente, simbolo=simbolo)
    return f"{sinal} {texto}"


def percentual(
    valor: Numerico | None,
    *,
    casas: int = 2,
    ausente: str = AUSENTE,
    remover_decimal_zero: bool = False,
    simbolo: bool = True,
) -> str:
    """``12,34 %``. Recebe o número já em pontos percentuais, não a fração.

    ``casas`` alto e ``remover_decimal_zero`` cobrem o caso do MegaSena, que
    mostra probabilidade com até oito casas e corta os zeros à direita — uma
    chance de 1 em 50 milhões some inteira com duas casas.
    """
    if valor is None:
        return ausente
    texto = numero(
        valor,
        casas=casas,
        ausente=ausente,
        remover_decimal_zero=remover_decimal_zero,
    )
    if remover_decimal_zero and "," in texto:
        texto = texto.rstrip("0").rstrip(",")
    return f"{texto} %" if simbolo else texto
