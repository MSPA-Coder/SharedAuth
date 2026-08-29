"""Acesso padrão-nega: toda rota exige sessão, exceto endpoints públicos.

Rotas novas nascem protegidas. Sessões expiradas podem gerar ``HX-Redirect``
para HTMX, 401 JSON para APIs ou redirecionamento HTML, conforme a configuração.
"""

from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Callable, TypeVar

from flask import abort, jsonify, make_response, redirect, request, url_for

if TYPE_CHECKING:
    from flask import Flask, Response


_MARCA_REGISTRO = "sharedauth_access_registrado"

F = TypeVar("F", bound=Callable[..., object])


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


def requer_papel(
    tem_papel: Callable[[], bool],
    *,
    prefixo_api: str | None = "/api/",
    chave_erro_api: str = "error",
    mensagem: str = "Acesso restrito.",
) -> Callable[[F], F]:
    """Devolve um decorator que recusa com 403 quem não tem o papel.

    ``tem_papel`` é chamada a cada requisição da rota decorada — tipicamente
    ``lambda: current_user.is_admin``. Como em :func:`requer_login`, o
    Flask-Login não é importado aqui, para não forçar essa dependência em quem
    não a usa. **Nenhum modelo de papel entra nesta biblioteca**: quem decide
    o que é ter o papel é o consumidor.

    **403, nunca redirecionamento para o login.** Quem chega numa rota
    decorada já está autenticado — foi :func:`requer_login` que o deixou
    passar. Mandar essa pessoa para a tela de login sugeriria que entrar de
    novo resolveria, e não resolve: falta permissão, não sessão.

    Isto cobre a verificação **binária** de papel na camada de view. Modelos
    ricos — permissão por titular, área por endpoint — continuam no
    consumidor, porque não são casos particulares um do outro.

    Esconder o botão no template é apresentação, não controle: um item ausente
    do menu não impede ninguém de chamar a rota direto.

    **A recusa usa ``abort``, não um ``return`` da resposta.** A diferença
    importa: ``abort`` levanta a exceção HTTP, e é isso que deixa um
    ``errorhandler(403)`` do consumidor renderizar a página de erro do próprio
    aplicativo. Devolver a resposta pronta daqui passaria por cima desse
    handler e entregaria um 403 cru, sem a casca visual do app — foi o que a
    suíte do ControleRendaVariavel apanhou na primeira versão deste contrato.
    """

    def decorador(view: F) -> F:
        @wraps(view)
        def wrapper(*args: object, **kwargs: object):
            if tem_papel():
                return view(*args, **kwargs)
            if prefixo_api and request.path.startswith(prefixo_api):
                # `abort` aceita um Response pronto e o levanta como está: a
                # rota de API recusa em JSON sem depender de o consumidor ter
                # um handler que saiba distinguir API de HTML.
                abort(make_response(jsonify({chave_erro_api: mensagem}), 403))
            abort(403, description=mensagem)

        return wrapper  # type: ignore[return-value]

    return decorador
