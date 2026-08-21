"""Rotinas de base compartilhadas entre os apps do mantenedor.

Não é framework novo: é o que ConfortoTermico, MegaSena, ControleBancario e
ControleRendaVariavel já faziam cada um por conta própria — sessão, CSRF,
limite de tentativas, hash de senha, controle de acesso por padrão-nega,
mensagens de status, cabeçalhos de segurança, formatação de números em
pt-BR e rota de saúde — extraído uma vez para não divergir de novo por
acidente, como divergiu (ver PLANO_UNIFICAR_AUTENTICACAO.md e
PLANO_EQUALIZAR_BASE_COMPARTILHADA.md no repositório _manutencao dos outros
projetos).

O nome do pacote é anterior a metade do que ele cobre hoje. Renomear
quebraria os imports e o encanamento de token/CI dos três apps Flask por
ganho cosmético — decisão registrada, não descuido.

**Dois níveis de instalação**, e a divisão é proposital:

  - ``sharedauth`` — núcleo sem dependência nenhuma: :mod:`~sharedauth.security`
    e :mod:`~sharedauth.formatting`. É o que o ControleBancario (Django)
    instala, para compartilhar a política de cabeçalhos e a conta de
    formatação sem arrastar um framework web que ele não usa.
  - ``sharedauth[flask]`` — o resto, que fala com Flask/Werkzeug.

Um módulo do núcleo que passe a importar Flask quebra o ControleBancario na
instalação, não em runtime, e por isso existe um teste que verifica isso
(``tests/test_nucleo_sem_flask.py``).

O que este pacote deliberadamente NÃO faz:
  - não decide o modelo de autorização de nenhum app (papéis, permissões);
    isso continua em cada projeto, porque a necessidade real é diferente
    em cada um;
  - não decide identidade visual: cada app tem paleta própria de propósito;
  - não é um serviço de login único (SSO); executa dentro do processo do
    próprio app, como sempre fez.
"""

from __future__ import annotations

__version__ = "0.3.0"
