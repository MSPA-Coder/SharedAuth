"""Padrão-nega: toda rota exige sessão, exceto a lista curta que não exige.

Os dois apps que já usam Flask-Login (MegaSena, ControleRendaVariavel) tinham
o mesmo desenho, escrito duas vezes: uma lista de endpoints *públicos* (nunca
de endpoints protegidos, de propósito — uma rota nova nasce protegida) e um
``before_request`` que barra o resto. As duas implementações reagiam
diferente quando a sessão expirava no meio de uma resposta HTMX: uma devolvia
``HX-Redirect`` (recarrega a página inteira), a outra devolvia 401 JSON para
chamadas de API. Este módulo aceita as duas formas, escolhida por app.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from flask import jsonify, make_response, redirect, request, url_for

if TYPE_CHECKING:
    from flask import Flask, Response


def requer_login(
    app: Flask,
    *,
    endpoints_publicos: frozenset[str],
    endpoint_login: str,
    esta_autenticado: Callable[[], bool],
    prefixo_api: str | None = "/api/",
    usar_hx_redirect: bool = False,
) -> None:
    """Registra o ``before_request`` de padrão-nega.

    ``esta_autenticado`` é chamado a cada requisição — normalmente
    ``lambda: current_user.is_authenticated`` do Flask-Login. Não importamos
    Flask-Login aqui para não forçar essa dependência em quem não a usa.

    Uma sessão expirada durante requisição HTMX não pode devolver a tela de
    login dentro de um fragmento parcial:

    - ``usar_hx_redirect=True`` — cabeçalho ``HX-Redirect`` (o padrão do
      MegaSena), o navegador recarrega a página inteira no lugar certo;
    - ``usar_hx_redirect=False`` (padrão) — 401 JSON quando o caminho começa
      com ``prefixo_api`` (o padrão do ControleRendaVariavel), redirect HTML
      nos demais casos.
    """

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
            return jsonify(erro="Autenticação necessária."), 401

        return redirect(url_for(endpoint_login, next=request.full_path))
