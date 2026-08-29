"""Contratos de `sharedauth.logs`."""

from __future__ import annotations

import pytest

from sharedauth.logs import MARCA_REDIGIDA, TAMANHO_MAXIMO, sanitizar_log

# ---------------------------------------------------------------------------
# Injeção de linha -- o motivo principal do módulo
# ---------------------------------------------------------------------------


def test_quebra_de_linha_nao_cria_uma_segunda_linha() -> None:
    """Quem controla o valor nao pode controlar o que parece ser um registro.

    Sem isto, um login forjado vira duas linhas no log, e a segunda e
    indistinguivel de um registro verdadeiro -- justamente para quem for ler o
    log depois de um incidente.
    """
    forjado = "joao\n2026-08-29 03:00:00 INFO login bem-sucedido usuario=admin"

    limpo = sanitizar_log(forjado)

    assert "\n" not in limpo
    assert "joao" in limpo


@pytest.mark.parametrize("controle", ["\r", "\n", "\r\n", "\x00", "\x1b", "\x7f", "\v", "\f"])
def test_todo_caractere_de_controle_vira_espaco(controle: str) -> None:
    limpo = sanitizar_log(f"antes{controle}depois")

    assert controle not in limpo
    assert limpo.startswith("antes")
    assert limpo.endswith("depois")


def test_tabulacao_e_preservada() -> None:
    """`\\t` e separador legitimo em log tabular -- nao e ruido a limpar."""
    assert sanitizar_log("a\tb") == "a\tb"


# ---------------------------------------------------------------------------
# Credencial
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entrada",
    [
        "senha=hunter2",
        "senha: hunter2",
        "password=hunter2",
        "PASSWORD = hunter2",
        "db_password=hunter2",
        "secret=hunter2",
        "token=hunter2",
        "api_key=hunter2",
        "X-Auth-Token: hunter2",
        '{"senha": "hunter2"}',
        "'password': 'hunter2'",
    ],
)
def test_valor_de_chave_sensivel_e_redigido(entrada: str) -> None:
    limpo = sanitizar_log(entrada)

    assert "hunter2" not in limpo
    assert MARCA_REDIGIDA in limpo


def test_a_chave_sobrevive_a_redacao() -> None:
    """Saber que havia uma senha ali e util; saber qual, nao."""
    limpo = sanitizar_log("usuario=ana senha=hunter2 acao=login")

    assert "usuario=ana" in limpo
    assert "senha=" in limpo
    assert "acao=login" in limpo
    assert "hunter2" not in limpo


def test_bearer_e_basic_sao_redigidos() -> None:
    """Nao tem `=` nem `:`, entao escapam da regra de atribuicao."""
    assert "abc.def.ghi" not in sanitizar_log("Authorization: Bearer abc.def.ghi")
    assert "dXNlcjpwYXNz" not in sanitizar_log("Basic dXNlcjpwYXNz")


def test_senha_dentro_da_url_de_conexao_e_redigida() -> None:
    """E como ela aparece numa excecao de driver -- o vazamento mais comum."""
    limpo = sanitizar_log(
        "could not connect: postgresql://investimentos:s3nh4Secreta@db:5432/base"
    )

    assert "s3nh4Secreta" not in limpo
    assert "investimentos" in limpo
    assert "db:5432/base" in limpo


def test_texto_sem_credencial_passa_intacto() -> None:
    mensagem = "posicao 42 encerrada por ana em 2026-08-29"

    assert sanitizar_log(mensagem) == mensagem


# ---------------------------------------------------------------------------
# Bordas
# ---------------------------------------------------------------------------


def test_valor_gigante_e_cortado() -> None:
    """Entrada de fora nao pode encher disco nem afogar as linhas vizinhas."""
    limpo = sanitizar_log("x" * (TAMANHO_MAXIMO * 3))

    assert len(limpo) < TAMANHO_MAXIMO + 20
    assert limpo.endswith("[cortado]")


@pytest.mark.parametrize(("entrada", "esperado"), [(None, "None"), (42, "42"), ("", "")])
def test_aceita_o_que_nao_e_texto(entrada: object, esperado: str) -> None:
    """Quem chama esta tratando entrada de fora; converter no ponto de uso e ruido."""
    assert sanitizar_log(entrada) == esperado


def test_a_funcao_nao_tem_efeito_colateral() -> None:
    """Descartar o retorno nao sanitiza nada -- e o erro mais facil de cometer.

    Foi exatamente o que aconteceu no unico uso que existia antes deste modulo:
    `sanitizar_log(login_digitado)` numa linha propria, resultado no lixo.
    """
    original = "senha=hunter2\ninjetado"
    copia = str(original)

    sanitizar_log(original)

    assert original == copia
    assert "hunter2" in original
