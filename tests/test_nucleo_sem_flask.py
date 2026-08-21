"""O núcleo tem que importar sem Flask — é o que o ControleBancario instala.

Não dá para testar isso no processo do pytest: o Flask já está importado por
causa dos outros testes. A verificação roda num interpretador limpo, onde
`sys.modules` só tem o que os módulos do núcleo trouxeram.

Se este teste falhar, o sintoma no ControleBancario não é um erro de runtime
tratável: é o `pip install sharedauth` do Django trazendo um framework web
inteiro, ou quebrando por dependência ausente.
"""

from __future__ import annotations

import subprocess
import sys


def test_security_e_formatting_nao_arrastam_flask_nem_werkzeug() -> None:
    codigo = (
        "import sys;"
        "import sharedauth, sharedauth.security, sharedauth.formatting;"
        # `sharedauth.ui` entra aqui porque e o pacote de interface, e a
        # razao de ele existir e o Django poder consumi-lo. Se ele passar a
        # importar Flask no topo, o ControleBancario quebra no import -- e
        # seria a terceira vez que o compartilhado para na fronteira do
        # framework (antes: `messages` e `/health`).
        "import sharedauth.ui;"
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
