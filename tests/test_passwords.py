from __future__ import annotations

import pytest

from sharedauth.passwords import (
    MIN_PASSWORD_LENGTH,
    ConfirmacaoNaoConfereError,
    SenhaAtualIncorretaError,
    SenhaMuitoCurtaError,
    SenhaNovaIgualAAtualError,
    conferir_hash,
    conferir_login,
    gerar_hash,
    gerar_senha_temporaria,
    validar_tamanho,
    validar_troca,
)


def test_piso_e_dez() -> None:
    assert MIN_PASSWORD_LENGTH == 10


def test_senha_curta_e_recusada() -> None:
    with pytest.raises(SenhaMuitoCurtaError):
        validar_tamanho("1234567")  # 7 caracteres


def test_senha_abaixo_do_piso_novo_e_recusada() -> None:
    # O piso subiu de 8 para 10; 9 caracteres passava antes e não passa mais.
    with pytest.raises(SenhaMuitoCurtaError):
        validar_tamanho("123456789")  # 9 caracteres


def test_senha_no_piso_passa() -> None:
    validar_tamanho("1234567890")  # 10 caracteres, não levanta


def test_gerar_hash_recusa_senha_curta() -> None:
    with pytest.raises(SenhaMuitoCurtaError):
        gerar_hash("curta12")


def test_hash_e_verificacao_de_ponta_a_ponta() -> None:
    hash_ = gerar_hash("Admin@2026")
    assert conferir_hash(hash_, "Admin@2026") is True
    assert conferir_hash(hash_, "outra-senha") is False


def test_hash_nunca_e_a_senha_em_texto_puro() -> None:
    hash_ = gerar_hash("Admin@2026")
    assert "Admin@2026" not in hash_


def test_conferir_com_hash_none_devolve_falso_sem_levantar() -> None:
    # Conta sem senha definida ainda (importação administrativa, conta só
    # de token) -- recusar a senha, não derrubar o login com 500.
    assert conferir_hash(None, "qualquer-senha") is False


def test_conferir_com_hash_vazio_devolve_falso_sem_levantar() -> None:
    assert conferir_hash("", "qualquer-senha") is False


# --- senha temporária entregue pelo administrador -------------------------


def test_senha_temporaria_respeita_o_piso() -> None:
    assert len(gerar_senha_temporaria()) >= MIN_PASSWORD_LENGTH
    validar_tamanho(gerar_senha_temporaria())


def test_senha_temporaria_recusa_tamanho_abaixo_do_piso() -> None:
    with pytest.raises(SenhaMuitoCurtaError):
        gerar_senha_temporaria(MIN_PASSWORD_LENGTH - 1)


def test_senha_temporaria_nao_usa_caracteres_ambiguos() -> None:
    # Ela vai ser ditada por telefone: "0" e "O" viram a mesma coisa.
    ambiguos = set("0O1lI")
    for _ in range(200):
        assert not (set(gerar_senha_temporaria()) & ambiguos)


def test_duas_senhas_temporarias_nao_se_repetem() -> None:
    # Não é teste de aleatoriedade (não dá para testar isso assim); é a
    # detecção de um valor fixo devolvido por engano.
    assert len({gerar_senha_temporaria() for _ in range(50)}) == 50


def test_senha_temporaria_serve_para_gerar_hash() -> None:
    senha = gerar_senha_temporaria()
    assert conferir_hash(gerar_hash(senha), senha) is True


# --- troca feita pelo próprio dono ----------------------------------------


def test_troca_valida_nao_levanta() -> None:
    validar_troca(
        hash_atual=gerar_hash("senha-antiga"),
        senha_atual="senha-antiga",
        senha_nova="senha-nova-1",
        confirmacao="senha-nova-1",
    )


def test_troca_com_senha_atual_errada_e_recusada() -> None:
    with pytest.raises(SenhaAtualIncorretaError):
        validar_troca(
            hash_atual=gerar_hash("senha-antiga"),
            senha_atual="chute-errado",
            senha_nova="senha-nova-1",
            confirmacao="senha-nova-1",
        )


def test_troca_confere_a_senha_atual_antes_de_tudo() -> None:
    # Com a senha atual errada E a confirmação divergente, o erro tem de ser o
    # da senha atual: quem não sabe a senha não aprende nada sobre o que
    # tentou colocar no lugar.
    with pytest.raises(SenhaAtualIncorretaError):
        validar_troca(
            hash_atual=gerar_hash("senha-antiga"),
            senha_atual="chute-errado",
            senha_nova="senha-nova-1",
            confirmacao="outra-coisa",
        )


def test_troca_com_confirmacao_divergente_e_recusada() -> None:
    with pytest.raises(ConfirmacaoNaoConfereError):
        validar_troca(
            hash_atual=gerar_hash("senha-antiga"),
            senha_atual="senha-antiga",
            senha_nova="senha-nova-1",
            confirmacao="senha-nova-2",
        )


def test_troca_para_a_mesma_senha_e_recusada() -> None:
    # O caso real: a pessoa obrigada a trocar redigita a senha temporária que
    # o administrador ditou. A marca se apagaria e a senha que um terceiro
    # conhece continuaria valendo.
    with pytest.raises(SenhaNovaIgualAAtualError):
        validar_troca(
            hash_atual=gerar_hash("senha-temporaria"),
            senha_atual="senha-temporaria",
            senha_nova="senha-temporaria",
            confirmacao="senha-temporaria",
        )


def test_troca_para_senha_curta_e_recusada() -> None:
    with pytest.raises(SenhaMuitoCurtaError):
        validar_troca(
            hash_atual=gerar_hash("senha-antiga"),
            senha_atual="senha-antiga",
            senha_nova="curta12",
            confirmacao="curta12",
        )


def test_troca_com_hash_ausente_e_recusada_sem_levantar_de_dentro() -> None:
    # Conta sem senha definida: recusar como "senha atual inválida", nunca
    # deixar passar por o hash ser nulo.
    with pytest.raises(SenhaAtualIncorretaError):
        validar_troca(
            hash_atual=None,
            senha_atual="",
            senha_nova="senha-nova-1",
            confirmacao="senha-nova-1",
        )


def test_erros_de_troca_sao_todos_value_error() -> None:
    # O consumidor que só quer uma mensagem captura a família inteira.
    for erro in (
        SenhaAtualIncorretaError,
        ConfirmacaoNaoConfereError,
        SenhaNovaIgualAAtualError,
        SenhaMuitoCurtaError,
    ):
        assert issubclass(erro, ValueError)


# --- conferir_login: o scrypt roda em todos os caminhos --------------------


@pytest.fixture
def chamadas_de_hash(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from werkzeug import security

    chamadas: list[str] = []
    original = security.check_password_hash

    def espiao(hash_: str, senha: str) -> bool:
        chamadas.append(hash_)
        return original(hash_, senha)

    monkeypatch.setattr(security, "check_password_hash", espiao)
    return chamadas


@pytest.mark.parametrize("ausente", [None, ""])
def test_login_sem_hash_paga_o_hash_e_recusa(
    chamadas_de_hash: list[str], ausente: str | None
) -> None:
    assert conferir_login(ausente, "qualquer-senha") is False
    assert len(chamadas_de_hash) == 1


def test_login_inativo_paga_o_hash_e_recusa_senha_certa(
    chamadas_de_hash: list[str],
) -> None:
    hash_ = gerar_hash("senha-correta-123")
    assert conferir_login(hash_, "senha-correta-123", ativo=False) is False
    assert chamadas_de_hash == [hash_]


def test_login_ativo_aceita_a_senha_certa_e_recusa_a_errada(
    chamadas_de_hash: list[str],
) -> None:
    hash_ = gerar_hash("senha-correta-123")
    assert conferir_login(hash_, "senha-correta-123") is True
    assert conferir_login(hash_, "senha-errada-123") is False
    assert chamadas_de_hash == [hash_, hash_]


def test_login_com_hash_malformado_e_falso_sem_excecao() -> None:
    assert conferir_login("isto-nao-e-hash", "qualquer-senha") is False


def test_hash_de_equiparacao_nunca_confere_e_e_reaproveitado(
    chamadas_de_hash: list[str],
) -> None:
    conferir_login(None, "a")
    conferir_login(None, "b")
    assert chamadas_de_hash[0] == chamadas_de_hash[1]
