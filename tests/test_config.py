from __future__ import annotations

import pytest

from sharedauth.config import FlagInvalidaError, ler_flag, montar_url_postgres


# --------------------------------------------------------------------------
# ler_flag
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bruto", ["1", "true", "TRUE", " True ", "yes", "on", "sim"])
def test_valores_verdadeiros(bruto: str) -> None:
    assert ler_flag("FLAG", ambiente={"FLAG": bruto}) is True


@pytest.mark.parametrize("bruto", ["0", "false", "FALSE", " off ", "no", "nao", ""])
def test_valores_falsos(bruto: str) -> None:
    assert ler_flag("FLAG", ambiente={"FLAG": bruto}) is False


def test_ausente_devolve_o_padrao() -> None:
    assert ler_flag("FLAG", ambiente={}) is False
    assert ler_flag("FLAG", padrao=True, ambiente={}) is True


def test_ausente_nao_levanta_nem_no_modo_estrito() -> None:
    # Ausência não é erro: é a configuração não ter sido informada.
    assert ler_flag("FLAG", estrito=True, ambiente={}) is False


def test_valor_invalido_levanta_no_modo_estrito() -> None:
    with pytest.raises(FlagInvalidaError) as erro:
        ler_flag("RATE_LIMIT", ambiente={"RATE_LIMIT": "sim, por favor"})
    # A mensagem precisa nomear a variável: é o que transforma a falha de
    # inicialização em algo acionável para quem implanta.
    assert "RATE_LIMIT" in str(erro.value)


def test_estrito_e_o_padrao() -> None:
    # Um interruptor de segurança mal escrito precisa derrubar a subida, não
    # virar False em silêncio. Se este teste falhar, a proteção passou a poder
    # ser desligada por um erro de digitação.
    with pytest.raises(FlagInvalidaError):
        ler_flag("FLAG", ambiente={"FLAG": "talvez"})


def test_valor_invalido_devolve_o_padrao_quando_tolerante() -> None:
    assert ler_flag("FLAG", estrito=False, ambiente={"FLAG": "talvez"}) is False
    assert ler_flag("FLAG", padrao=True, estrito=False, ambiente={"FLAG": "x"}) is True


def test_le_do_os_environ_quando_ambiente_nao_e_passado(monkeypatch) -> None:
    monkeypatch.setenv("SHAREDAUTH_TESTE_FLAG", "on")
    assert ler_flag("SHAREDAUTH_TESTE_FLAG") is True


# --------------------------------------------------------------------------
# montar_url_postgres
# --------------------------------------------------------------------------


def test_url_no_formato_esperado() -> None:
    url = montar_url_postgres(
        usuario="investimentos",
        senha="segredo",
        host="postgres",
        banco="investimentos",
        porta=5432,
    )
    assert url == "postgresql+psycopg://investimentos:segredo@postgres:5432/investimentos"


@pytest.mark.parametrize(
    ("senha", "escapado"),
    [
        ("com@arroba", "com%40arroba"),
        ("com/barra", "com%2Fbarra"),
        ("com:doispontos", "com%3Adoispontos"),
    ],
)
def test_senha_com_caractere_estrutural_e_escapada(senha: str, escapado: str) -> None:
    """O caso que quebra silenciosamente e aponta a conexão para outro lugar.

    Sem `quote(..., safe="")`, uma senha com `@` parte a URL no separador
    errado: o driver leria o resto da senha como host. Não falha como erro de
    escape — falha como "não conecta", ou pior, como mensagem de erro do
    driver carregando parte do segredo.
    """
    url = montar_url_postgres(
        usuario="u", senha=senha, host="db", banco="b", porta=5432
    )
    assert url == f"postgresql+psycopg://u:{escapado}@db:5432/b"
    # O caractere cru não pode sobrar em lugar nenhum depois do "u:".
    assert senha not in url


def test_usuario_e_banco_tambem_sao_escapados() -> None:
    url = montar_url_postgres(
        usuario="us er", senha="s", host="db", banco="ba/nco", porta=5432
    )
    assert "us%20er" in url
    assert "ba%2Fnco" in url


def test_ipv6_recebe_colchetes() -> None:
    # Sem os colchetes, o primeiro ":" do endereço vira separador de porta.
    url = montar_url_postgres(usuario="u", senha="s", host="::1", banco="b")
    assert url == "postgresql+psycopg://u:s@[::1]:5432/b"


def test_ipv6_ja_com_colchetes_nao_e_duplicado() -> None:
    url = montar_url_postgres(usuario="u", senha="s", host="[::1]", banco="b")
    assert "[[" not in url


def test_driver_pode_ser_trocado() -> None:
    url = montar_url_postgres(
        usuario="u", senha="s", host="db", banco="b", driver="postgresql"
    )
    assert url.startswith("postgresql://")


def test_porta_como_texto_e_aceita() -> None:
    url = montar_url_postgres(usuario="u", senha="s", host="db", banco="b", porta="5302")
    assert url.endswith(":5302/b")


@pytest.mark.parametrize("porta", ["abc", 0, 70000, None])
def test_porta_invalida_recusada(porta) -> None:
    with pytest.raises(ValueError):
        montar_url_postgres(usuario="u", senha="s", host="db", banco="b", porta=porta)


@pytest.mark.parametrize("faltando", ["usuario", "host", "banco"])
def test_componente_obrigatorio_ausente_recusado(faltando: str) -> None:
    argumentos = {"usuario": "u", "senha": "s", "host": "db", "banco": "b"}
    argumentos[faltando] = ""
    with pytest.raises(ValueError, match=faltando):
        montar_url_postgres(**argumentos)


def test_senha_vazia_e_aceita() -> None:
    # Não é papel deste módulo exigir senha: há arranjos com `trust` local.
    # Quem decide se a senha é obrigatória é o consumidor.
    url = montar_url_postgres(usuario="u", senha="", host="db", banco="b")
    assert url == "postgresql+psycopg://u:@db:5432/b"
