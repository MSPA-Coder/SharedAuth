"""Cabeçalhos defensivos e Content-Security-Policy — um conjunto, quatro apps.

O comentário que existia acima deste dicionário no ConfortoTermico e no
MegaSena dizia, palavra por palavra nos dois, que "manter igual em todos é o
que permite auditar um e confiar nos demais". O comentário foi copiado junto
com o código, e mesmo assim as cópias divergiram: o ControleBancario liberava
`font-src data:` sem ter nenhuma fonte embutida, e o ControleRendaVariavel
declarava um `Permissions-Policy` com uma diretiva a mais que os outros três.
É exatamente o tipo de deriva silenciosa que só some quando existe um lugar
só onde o valor é escrito.

**Este módulo é Python puro — não importa Flask nem Werkzeug em tempo de
execução.** Isso é deliberado: o ControleBancario é Django e precisa
importar :data:`SECURITY_HEADERS` e :func:`montar_csp` sem arrastar um
framework web inteiro que ele não usa. Só :func:`registrar_cabecalhos` fala
com o Flask, e ela recebe o app pronto em vez de importá-lo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - só para tipagem
    from flask import Blueprint, Flask

# `Referrer-Policy` é `same-origin`, não `no-referrer`: sob `no-referrer` o
# navegador serializa o cabeçalho `Origin` como `null` também em POST de mesma
# origem (Fetch spec), e qualquer verificação de CSRF que consulte `Origin` —
# como a do Django, no projeto irmão — passa a recusar a requisição com o
# token correto. `same-origin` não vaza referrer para fora da origem, que é o
# que importa, e preserva o `Origin`.
#
# `browsing-topics=()` veio do ControleRendaVariavel, onde o Flask-Talisman o
# escrevia sozinho. É estritamente mais restritivo que não declarar nada
# (recusa a Topics API do Chrome), então subiu para o conjunto comum em vez de
# ser descartado junto com o Talisman.
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": (
        "camera=(), microphone=(), geolocation=(), browsing-topics=()"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
}


def montar_csp(*, imagens_data_uri: bool = False) -> str:
    """Monta a política. O padrão é o mais fechado que os apps toleram.

    Nenhum dos apps usa `<style>`, `style=` ou `<script>` inline, então
    `style-src`/`script-src` fecham em `'self'` sem exceção: um XSS refletido
    não consegue injetar nem estilo nem script. Quem quiser altura de barra
    proporcional num gráfico usa classe CSS estática, como o MegaSena passou a
    fazer — não mutação de estilo em runtime.

    ``imagens_data_uri`` abre `img-src` para `data:`. **Só ligue com motivo
    escrito no ponto da chamada.** Hoje o motivo real é um só: MegaSena e
    ControleBancario declaram o favicon como SVG embutido no `<link rel=icon>`
    do `base.html`. ConfortoTermico e ControleRendaVariavel não têm favicon
    nenhum e ficam com a política fechada — consolidar as quatro políticas
    numa só não pode virar a união delas, que seria mais permissiva que
    qualquer uma das quatro.
    """
    img_src = "'self' data:" if imagens_data_uri else "'self'"
    return "; ".join(
        (
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self'",
            f"img-src {img_src}",
            "font-src 'self'",
            "connect-src 'self'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
        )
    )


#: A política fechada, pronta para quem não precisa de exceção nenhuma.
CONTENT_SECURITY_POLICY = montar_csp()


def registrar_cabecalhos(
    alvo: Flask | Blueprint,
    *,
    imagens_data_uri: bool = False,
) -> None:
    """Aplica :data:`SECURITY_HEADERS` e a CSP em toda resposta do app.

    Aceita um ``Flask`` ou um ``Blueprint``: o MegaSena pendura os cabeçalhos
    no blueprint principal (`after_app_request`), os outros dois no app
    (`after_request`). O efeito é o mesmo — toda resposta da aplicação — e não
    vale forçar os três a mudarem a forma de registrar por causa disso.

    Usa ``setdefault``: se o app já decidiu um valor para aquela resposta
    específica (uma rota que precise de `Cache-Control` próprio, por exemplo),
    o valor do app vence.
    """
    csp = montar_csp(imagens_data_uri=imagens_data_uri)

    def _aplicar_cabecalhos(resposta):
        for cabecalho, valor in SECURITY_HEADERS.items():
            resposta.headers.setdefault(cabecalho, valor)
        resposta.headers.setdefault("Content-Security-Policy", csp)
        return resposta

    registrar = getattr(alvo, "after_app_request", None) or alvo.after_request
    registrar(_aplicar_cabecalhos)
