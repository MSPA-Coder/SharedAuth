"""Acesso padrão-nega: toda rota exige sessão, exceto endpoints públicos.

Rotas novas nascem protegidas. Sessões expiradas podem gerar ``HX-Redirect``
para HTMX, 401 JSON para APIs ou redirecionamento HTML, conforme a configuração.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from flask import jsonify, make_response, redirect, request, url_for

if TYPE_CHECKING:
    from flask import Flask, Response


_MARCA_REGISTRO = "sharedauth_access_registrado"


def requer_login(
    app: Flask,
    *,
    endpoints_publicos: frozenset[str],
    endpoint_login: str,
    esta_autenticado: Callable[[], bool],
    prefixo_api: str | None = "/api/",
    usar_hx_redirect: bool = False,
    chave_erro_api: str = "error",
) -> None:
    """Registra o ``before_request`` de padrão-nega.

    ``esta_autenticado`` é chamado a cada requisição — normalmente
    ``lambda: current_user.is_authenticated`` do Flask-Login. Não importamos
    Flask-Login aqui para não forçar essa dependência em quem não a usa.

    Uma sessão expirada durante requisição HTMX não pode devolver a tela de
    login dentro de um fragmento parcial:

    - ``usar_hx_redirect=True`` — cabeçalho ``HX-Redirect`` para o navegador
      recarregar a página inteira;
    - ``usar_hx_redirect=False`` (padrão) — 401 JSON quando o caminho começa
      com ``prefixo_api`` e redirect HTML nos demais casos.

    ``chave_erro_api`` define a chave do corpo JSON do 401 e pode ser
    sobrescrita pelo consumidor.

    Levanta ``RuntimeError`` se chamada mais de uma vez no mesmo app: o
    Flask não deduplica ``before_request``, e uma segunda chamada com
    parâmetros diferentes tornaria a primeira silenciosamente vencedora para
    qualquer rota que ela já resolvesse — perigoso demais para passar em
    silêncio num controle de acesso.
    """
    if app.extensions.get(_MARCA_REGISTRO):
        raise RuntimeError(
            "requer_login já foi registrado neste app. Chamar de novo "
            "tornaria a primeira chamada silenciosamente vencedora para "
            "parte das rotas — corrija o app para chamar uma vez só."
        )
    app.extensions[_MARCA_REGISTRO] = True

    @app.before_request
    def _requer_login() -> Response | None:
        if request.endpoint is None or request.endpoint in endpoints_publicos:
            return None
        if esta_autenticado():
            return None

        if usar_hx_redirect and request.headers.get("HX-Request", "").lower() == "true":
            resposta = make_response("", 401)
            resposta.headers["HX-Redirect"] = url_for(endpoint_login)
            return resposta

        if prefixo_api and request.path.startswith(prefixo_api):
            return jsonify({chave_erro_api: "Autenticação necessária."}), 401

        # request.full_path do Werkzeug sempre termina em "?", mesmo sem
        # query string -- evitar isso aqui em vez de propagar "?next=/x%3F".
        proximo = request.full_path if request.query_string else request.path
        return redirect(url_for(endpoint_login, next=proximo))
