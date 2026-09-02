from __future__ import annotations

from pathlib import Path

import pytest

from sharedauth.secrets import (
    SegredoInvalidoError,
    ler_arquivo_de_segredo,
    resolver_segredo,
)

VALOR = "s3gr3d0-de-teste"


@pytest.fixture
def arquivo_de_segredo(tmp_path: Path) -> Path:
    caminho = tmp_path / "secret_key"
    caminho.write_text(f"{VALOR}\n", encoding="utf-8")
    return caminho


# --------------------------------------------------------------------------
# ler_arquivo_de_segredo
# --------------------------------------------------------------------------


def test_le_o_valor_sem_a_quebra_de_linha_final(arquivo_de_segredo: Path) -> None:
    # Um editor que acrescenta "\n" no fim não pode mudar o segredo.
    assert ler_arquivo_de_segredo("SECRET_KEY_FILE", arquivo_de_segredo) == VALOR


def test_arquivo_ausente_e_recusado(tmp_path: Path) -> None:
    with pytest.raises(SegredoInvalidoError):
        ler_arquivo_de_segredo("SECRET_KEY_FILE", tmp_path / "nao-existe")


def test_arquivo_vazio_e_recusado(tmp_path: Path) -> None:
    vazio = tmp_path / "vazio"
    vazio.write_text("   \n", encoding="utf-8")
    with pytest.raises(SegredoInvalidoError, match="vazio"):
        ler_arquivo_de_segredo("SECRET_KEY_FILE", vazio)


def test_caminho_esperado_aceita_o_alvo_declarado(arquivo_de_segredo: Path) -> None:
    assert (
        ler_arquivo_de_segredo(
            "SECRET_KEY_FILE", arquivo_de_segredo, caminho_esperado=arquivo_de_segredo
        )
        == VALOR
    )


def test_caminho_esperado_recusa_outro_arquivo(tmp_path: Path) -> None:
    """A propriedade de segurança central deste módulo.

    Sem `caminho_esperado`, a variável `NOME_FILE` deixa de ser configuração
    de implantação e vira seletor arbitrário de arquivo: quem controla o
    ambiente do processo aponta para qualquer arquivo legível e o conteúdo
    entra na aplicação como se fosse o segredo.
    """
    esperado = tmp_path / "secret_key"
    esperado.write_text(VALOR, encoding="utf-8")
    outro = tmp_path / "qualquer-outro-arquivo"
    outro.write_text("conteudo que nao e o segredo", encoding="utf-8")

    with pytest.raises(SegredoInvalidoError, match="deve apontar para"):
        ler_arquivo_de_segredo("SECRET_KEY_FILE", outro, caminho_esperado=esperado)


def test_caminho_esperado_nao_e_contornado_por_travessia(tmp_path: Path) -> None:
    # A comparação é sobre os caminhos resolvidos dos dois lados, então um
    # ".." no meio não muda o veredito.
    esperado = tmp_path / "secret_key"
    esperado.write_text(VALOR, encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    rodeio = sub / ".." / "secret_key"

    assert ler_arquivo_de_segredo(
        "SECRET_KEY_FILE", rodeio, caminho_esperado=esperado
    ) == VALOR


def test_mensagem_de_erro_nunca_contem_o_segredo(tmp_path: Path) -> None:
    """Exigência do módulo, não detalhe.

    Uma exceção com o segredo dentro viaja para o log de erro, para o terminal
    de quem implanta e, num app com traceback ligado, para a resposta HTTP.
    """
    esperado = tmp_path / "secret_key"
    esperado.write_text(VALOR, encoding="utf-8")
    outro = tmp_path / "outro"
    outro.write_text(VALOR, encoding="utf-8")

    with pytest.raises(SegredoInvalidoError) as erro:
        ler_arquivo_de_segredo("SECRET_KEY_FILE", outro, caminho_esperado=esperado)
    assert VALOR not in str(erro.value)


# --------------------------------------------------------------------------
# resolver_segredo
# --------------------------------------------------------------------------


def test_arquivo_tem_precedencia_sobre_a_variavel_direta(arquivo_de_segredo: Path) -> None:
    """Quando as duas existem, a do Compose vence.

    A concedida por arquivo é a operacional; a direta é sobra de execução
    manual. Deixar a direta ganhar faria uma sobra no ambiente substituir o
    segredo de produção em silêncio.
    """
    ambiente = {
        "SECRET_KEY_FILE": str(arquivo_de_segredo),
        "SECRET_KEY": "sobra-de-execucao-manual",
    }
    assert resolver_segredo("SECRET_KEY", ambiente=ambiente) == VALOR


def test_variavel_direta_usada_quando_nao_ha_arquivo() -> None:
    assert resolver_segredo("SECRET_KEY", ambiente={"SECRET_KEY": "direto"}) == "direto"


def test_variavel_direta_recusada_quando_nao_aceita() -> None:
    valor = resolver_segredo(
        "SECRET_KEY", ambiente={"SECRET_KEY": "direto"}, aceitar_variavel=False
    )
    assert valor is None


def test_ausente_devolve_none() -> None:
    assert resolver_segredo("SECRET_KEY", ambiente={}) is None


def test_ausente_e_obrigatorio_levanta() -> None:
    with pytest.raises(SegredoInvalidoError, match="SECRET_KEY"):
        resolver_segredo("SECRET_KEY", ambiente={}, obrigatorio=True)


def test_mensagem_de_obrigatorio_diz_o_que_definir() -> None:
    with pytest.raises(SegredoInvalidoError) as erro:
        resolver_segredo("SECRET_KEY", ambiente={}, obrigatorio=True)
    assert "SECRET_KEY_FILE" in str(erro.value)


def test_mensagem_de_obrigatorio_nao_oferece_a_variavel_quando_ela_e_recusada() -> None:
    with pytest.raises(SegredoInvalidoError) as erro:
        resolver_segredo(
            "SECRET_KEY", ambiente={}, obrigatorio=True, aceitar_variavel=False
        )
    mensagem = str(erro.value)
    assert "SECRET_KEY_FILE" in mensagem
    assert "SECRET_KEY com o valor" not in mensagem


def test_arquivo_declarado_mas_vazio_e_erro_nao_ausencia() -> None:
    """Alguém quis conceder por arquivo e a concessão está quebrada.

    Cair no fallback aqui esconderia um erro de implantação.
    """
    ambiente = {"SECRET_KEY_FILE": "   ", "SECRET_KEY": "fallback"}
    with pytest.raises(SegredoInvalidoError, match="não pode estar vazio"):
        resolver_segredo("SECRET_KEY", ambiente=ambiente)


def test_caminho_esperado_e_repassado(tmp_path: Path) -> None:
    esperado = tmp_path / "secret_key"
    esperado.write_text(VALOR, encoding="utf-8")
    outro = tmp_path / "outro"
    outro.write_text(VALOR, encoding="utf-8")

    with pytest.raises(SegredoInvalidoError, match="deve apontar para"):
        resolver_segredo(
            "SECRET_KEY",
            ambiente={"SECRET_KEY_FILE": str(outro)},
            caminho_esperado=esperado,
        )


def test_le_do_os_environ_quando_ambiente_nao_e_passado(monkeypatch) -> None:
    monkeypatch.setenv("SHAREDAUTH_TESTE_SEGREDO", "valor-do-ambiente")
    assert resolver_segredo("SHAREDAUTH_TESTE_SEGREDO") == "valor-do-ambiente"


# --------------------------------------------------------------------------
# resolver_segredo: valores_recusados e comprimento_minimo (SA-04)
# --------------------------------------------------------------------------


def test_valor_direto_recusado_por_ser_de_exemplo() -> None:
    with pytest.raises(SegredoInvalidoError, match="exemplo"):
        resolver_segredo(
            "SECRET_KEY",
            ambiente={"SECRET_KEY": "troque-por-um-segredo-forte"},
            valores_recusados=frozenset({"troque-por-um-segredo-forte"}),
        )


def test_valor_direto_fora_da_lista_recusada_passa() -> None:
    assert (
        resolver_segredo(
            "SECRET_KEY",
            ambiente={"SECRET_KEY": "um-valor-qualquer-que-nao-e-exemplo"},
            valores_recusados=frozenset({"troque-por-um-segredo-forte"}),
        )
        == "um-valor-qualquer-que-nao-e-exemplo"
    )


def test_valor_de_arquivo_tambem_e_checado_contra_recusados(
    tmp_path: Path,
) -> None:
    # Um placeholder copiado para dentro do arquivo montado é igualmente
    # inválido -- a checagem não pode valer só para a variável direta.
    caminho = tmp_path / "secret_key"
    caminho.write_text("troque-por-um-segredo-forte", encoding="utf-8")
    with pytest.raises(SegredoInvalidoError, match="exemplo"):
        resolver_segredo(
            "SECRET_KEY",
            ambiente={"SECRET_KEY_FILE": str(caminho)},
            valores_recusados=frozenset({"troque-por-um-segredo-forte"}),
        )


def test_mensagem_de_valor_recusado_nao_contem_o_valor() -> None:
    with pytest.raises(SegredoInvalidoError) as erro:
        resolver_segredo(
            "SECRET_KEY",
            ambiente={"SECRET_KEY": "troque-por-um-segredo-forte"},
            valores_recusados=frozenset({"troque-por-um-segredo-forte"}),
        )
    assert "troque-por-um-segredo-forte" not in str(erro.value)


def test_comprimento_minimo_recusa_valor_curto() -> None:
    with pytest.raises(SegredoInvalidoError, match="10"):
        resolver_segredo(
            "SECRET_KEY", ambiente={"SECRET_KEY": "curto"}, comprimento_minimo=10
        )


def test_comprimento_minimo_aceita_valor_exatamente_no_piso() -> None:
    assert (
        resolver_segredo(
            "SECRET_KEY",
            ambiente={"SECRET_KEY": "1234567890"},
            comprimento_minimo=10,
        )
        == "1234567890"
    )


def test_sem_valores_recusados_nem_comprimento_minimo_nao_muda_comportamento() -> None:
    # Compatibilidade: quem não passa os parâmetros novos não é afetado.
    assert resolver_segredo("SECRET_KEY", ambiente={"SECRET_KEY": "x"}) == "x"
