"""O núcleo deve ser importável sem Flask ou dependências de integração.

Não dá para testar isso no processo do pytest: o Flask já está importado por
causa dos outros testes. A verificação roda num interpretador limpo, onde
`sys.modules` só tem o que os módulos do núcleo trouxeram.

Uma falha indica que a instalação do núcleo passou a carregar um framework web
ou a depender de um pacote ausente.
"""

from __future__ import annotations

import subprocess
import sys


def test_security_e_formatting_nao_arrastam_flask_nem_werkzeug() -> None:
    codigo = (
        "import sys;"
        "import sharedauth, sharedauth.security, sharedauth.formatting;"
        # `config` le ambiente e monta URL de conexao em Python puro.
        "import sharedauth.config;"
        # `secrets` le arquivo e ambiente, sem framework.
        "import sharedauth.secrets;"
        # `sharedauth.ui` expõe assets sem exigir a integração Flask.
        "import sharedauth.ui;"
        # `logs` sanitiza texto de terceiro; só `re`.
        "import sharedauth.logs;"
        "proibidos = [m for m in sys.modules if m.split('.')[0] in "
        "('flask', 'werkzeug', 'flask_wtf', 'flask_limiter')];"
        "print(','.join(sorted(proibidos)))"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        check=True,
        # O subprocesso não lê nada. Sem isto, sob captura do pytest no
        # Windows, o Popen falha ao duplicar o handle de stdin e o teste pisca:
        # passa isolado e reprova na suíte completa, por um motivo que não tem
        # relação nenhuma com o que ele verifica.
        stdin=subprocess.DEVNULL,
    )
    assert resultado.stdout.strip() == "", (
        "o núcleo passou a importar um módulo de framework web: "
        f"{resultado.stdout.strip()}"
    )
