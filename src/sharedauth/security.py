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
#: Cabeçalho pelo qual uma resposta HTML pode variar sem mudar de URL.
#:
#: Nestes aplicativos, uma tela e o fragmento que a atualiza **compartilham a
#: URL de propósito**: é o que mantém a navegação sem JavaScript como caminho
#: completo, e o endereço válido para F5, favorito e link. O preço é que a
#: mesma URL passa a ter duas representações, escolhidas por este cabeçalho.
#:
#: Sem ``Vary``, um cache no caminho pode guardar o fragmento e servi-lo à
#: requisição seguinte como se fosse o documento inteiro — a tela aparece sem
#: casca, sem menu e sem scripts. O sintoma é intermitente e some ao recarregar,
#: que é a pior combinação para se descobrir a causa.
#:
#: Nenhuma implantação atual põe cache na frente (o Nginx faz proxy sem
#: ``proxy_cache``), então isto não corrige um defeito visível hoje: fecha uma
#: armadilha para quem um dia acrescentar uma CDN, um ``proxy_cache`` ou um
#: Service Worker sem saber deste detalhe.
CABECALHO_DE_APRESENTACAO = "HX-Request"

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
    hsts_segundos: int | None = None,
) -> None:
    """Aplica :data:`SECURITY_HEADERS` e a CSP em toda resposta do app.

    Aceita um ``Flask`` ou um ``Blueprint`` e aplica os cabeçalhos a toda
    resposta da aplicação.

    Usa ``setdefault``: se o app já decidiu um valor para aquela resposta
    específica (uma rota que precise de `Cache-Control` próprio, por exemplo),
    o valor do app vence.

    Toda resposta **HTML** ganha também ``Vary: HX-Request`` — ver
    :data:`CABECALHO_DE_APRESENTACAO`. Só HTML: acrescentá-lo aos estáticos
    faria um cache guardar duas cópias de cada arquivo sem nenhum ganho, já que
    nenhum estático é pedido por HTMX.

    ``hsts_segundos`` publica ``Strict-Transport-Security`` quando informado
    (``None``, o padrão, não publica nada). Passe a mesma flag de ambiente que
    o consumidor já usa para decidir ``SESSION_COOKIE_SECURE`` — sob HTTP puro
    de desenvolvimento, o navegador ignora o cabeçalho, mas ele não deveria ser
    emitido de qualquer forma. Um valor comum é ``15552000`` (180 dias). Esta
    função não acrescenta ``preload``: entrar na lista de preload do navegador
    é uma submissão manual e irreversível por domínio, decisão do consumidor,
    não desta biblioteca.
    """
    csp = montar_csp(imagens_data_uri=imagens_data_uri)

    def _aplicar_cabecalhos(resposta):
        for cabecalho, valor in SECURITY_HEADERS.items():
            resposta.headers.setdefault(cabecalho, valor)
        resposta.headers.setdefault("Content-Security-Policy", csp)
        if hsts_segundos is not None:
            resposta.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={hsts_segundos}; includeSubDomains",
            )
        if "text/html" in resposta.headers.get("Content-Type", ""):
            resposta.vary.add(CABECALHO_DE_APRESENTACAO)
        return resposta

    registrar = getattr(alvo, "after_app_request", None) or alvo.after_request
    registrar(_aplicar_cabecalhos)
