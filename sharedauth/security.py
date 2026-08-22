"""Cabeçalhos defensivos e Content-Security-Policy compartilhados.

O módulo é Python puro e não importa Flask ou Werkzeug em tempo de execução.
``registrar_cabecalhos`` recebe um alvo por tipagem estrutural.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - só para tipagem
    from flask import Blueprint, Flask

# `Referrer-Policy` é `same-origin`, não `no-referrer`: sob `no-referrer` o
# navegador serializa o cabeçalho `Origin` como `null` também em POST de mesma
# origem (Fetch spec), e qualquer verificação de CSRF que consulte `Origin` —
# como verificações baseadas em `Origin` — passa a recusar a requisição com o
# token correto. `same-origin` não vaza referrer para fora da origem e
# que importa, e preserva o `Origin`.
#
# `browsing-topics=()` recusa a Topics API do Chrome e é mais restritivo que
# omitir a diretiva.
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
    """Monta uma política fechada por padrão.

    `style-src` e `script-src` fecham em `'self'`: consumidores devem usar
    classes CSS e scripts externos, sem estilo ou script inline.

    ``imagens_data_uri`` abre `img-src` para `data:`. **Só ligue com motivo
    escrito no ponto da chamada.** Consumidores sem essa necessidade devem
    manter a política fechada em vez de adotar uma união mais permissiva.
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

    Aceita um ``Flask`` ou um ``Blueprint`` e aplica os cabeçalhos a toda
    resposta da aplicação.

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
