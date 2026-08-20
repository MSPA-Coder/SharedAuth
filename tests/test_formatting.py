from __future__ import annotations

from decimal import Decimal

from sharedauth.formatting import (
    AUSENTE,
    inteiro,
    moeda,
    moeda_com_sinal,
    numero,
    percentual,
)


def test_milhar_com_ponto_e_decimal_com_virgula() -> None:
    assert numero(Decimal("1234567.89")) == "1.234.567,89"


def test_valor_negativo_mantem_o_sinal_colado() -> None:
    assert numero(Decimal("-1234.56")) == "-1.234,56"


def test_float_nao_arrasta_erro_do_binario() -> None:
    # Decimal(0.1) guardaria 0.1000000000000000055511151231257827.
    assert numero(0.1, casas=3) == "0,100"


def test_ausencia_de_valor_e_diferente_de_zero() -> None:
    assert numero(None) == AUSENTE
    assert numero(Decimal("0")) == "0,00"


def test_ocultar_zero_deixa_a_celula_vazia() -> None:
    # Escolha do ControleBancario: uma tabela larga cheia de "R$ 0,00" só
    # gasta largura. Continua sendo escolha da tela, agora explícita.
    assert numero(Decimal("0"), ocultar_zero=True) == ""
    assert moeda(Decimal("0"), ocultar_zero=True) == ""


def test_remover_decimal_zero_corta_a_parte_inteira_redonda() -> None:
    assert numero(Decimal("1234.00"), remover_decimal_zero=True) == "1.234"
    assert numero(Decimal("1234.50"), remover_decimal_zero=True) == "1.234,50"


def test_inteiro_nao_tem_parte_decimal() -> None:
    assert inteiro(3044) == "3.044"


def test_moeda_traz_o_simbolo_separado_por_espaco() -> None:
    assert moeda(Decimal("1234.5")) == "R$ 1.234,50"


def test_moeda_aceita_outra_moeda() -> None:
    assert moeda(Decimal("10"), simbolo="US$") == "US$ 10,00"


def test_moeda_ausente_nao_ganha_simbolo() -> None:
    # "R$ -" seria pior que "-".
    assert moeda(None) == AUSENTE
    assert moeda(None, ausente="") == ""


def test_moeda_com_sinal_separa_o_sinal_do_valor() -> None:
    assert moeda_com_sinal(Decimal("10")) == "+ R$ 10,00"
    assert moeda_com_sinal(Decimal("-10")) == "- R$ 10,00"


def test_moeda_com_sinal_esconde_movimento_zerado() -> None:
    assert moeda_com_sinal(Decimal("0")) == ""


def test_percentual_padrao() -> None:
    assert percentual(Decimal("12.5")) == "12,50 %"


def test_percentual_sem_simbolo() -> None:
    assert percentual(Decimal("12.5"), simbolo=False) == "12,50"


def test_percentual_de_probabilidade_muito_pequena() -> None:
    # 1 em 50.063.860 (Mega-Sena, 6 dezenas). Com duas casas some inteira;
    # com oito sobrevive. Oito é o que o MegaSena já usava, e o resultado
    # aqui é igual ao dele, dígito por dígito.
    valor = Decimal("100") / Decimal("50063860")
    assert percentual(valor) == "0,00 %"
    assert percentual(valor, casas=8, remover_decimal_zero=True) == "0,000002 %"


def test_percentual_redondo_perde_os_zeros_a_direita() -> None:
    assert percentual(Decimal("25"), casas=8, remover_decimal_zero=True) == "25 %"
    assert percentual(Decimal("25.5"), casas=8, remover_decimal_zero=True) == "25,5 %"
