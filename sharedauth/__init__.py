"""Rotinas de login compartilhadas entre os apps Flask do mantenedor.

Não é framework de autenticação novo: é a mesma coisa que ConfortoTermico,
MegaSena e ControleRendaVariavel já faziam cada um por conta própria — sessão,
CSRF, limite de tentativas, hash de senha, controle de acesso por padrão-nega
e mensagens de status — extraída uma vez para não divergir de novo por
acidente, como divergiu (ver PLANO_UNIFICAR_AUTENTICACAO.md no repositório
_manutencao dos outros projetos).

O que este pacote deliberadamente NÃO faz:
  - não decide o modelo de autorização de nenhum app (papéis, permissões);
    isso continua em cada projeto, porque a necessidade real é diferente
    em cada um;
  - não é um serviço de login único (SSO); executa dentro do processo do
    próprio app, como sempre fez.
"""

from __future__ import annotations

__version__ = "0.1.0"
