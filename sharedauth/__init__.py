"""Contratos compartilhados de autenticação, segurança, formatação e interface.

O pacote não é um framework nem um serviço de login único. Ele oferece sessão,
CSRF, limite de tentativas, hash de senha, acesso padrão-nega, mensagens,
cabeçalhos de segurança, formatação pt-BR, rota de saúde e assets de interface.

**Dois níveis de instalação** preservam a fronteira de dependências:

  - ``sharedauth`` — núcleo sem dependências: :mod:`~sharedauth.security`,
    :mod:`~sharedauth.formatting`, :mod:`~sharedauth.config`,
    :mod:`~sharedauth.secrets` e
    :mod:`~sharedauth.ui` são importáveis sem carregar Flask ou Werkzeug;
  - ``sharedauth[flask]`` — o resto, que fala com Flask/Werkzeug.

``tests/test_nucleo_sem_flask.py`` verifica essa fronteira em um interpretador
limpo.

O que este pacote deliberadamente NÃO faz:
  - não decide modelos de autorização, papéis ou permissões;
  - não decide identidade visual; consumidores podem sobrescrever a paleta;
  - não é um serviço de login único (SSO); executa dentro do processo do
    próprio processo consumidor.
"""

from __future__ import annotations

__version__ = "0.7.0"
