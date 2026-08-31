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
_MARCA_TROCA_SENHA = "sharedauth_troca_senha_registrada"

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


def requer_troca_de_senha(
    app: Flask,
    *,
    endpoint_troca: str,
    endpoints_isentos: frozenset[str],
    esta_autenticado: Callable[[], bool],
    precisa_trocar: Callable[[], bool],
    prefixo_api: str | None = "/api/",
    usar_hx_redirect: bool = False,
    chave_erro_api: str = "error",
    mensagem_api: str = "Troca de senha obrigatória.",
) -> None:
    """Prende quem está com troca de senha pendente na tela de troca.

    Quando um administrador redefine a senha de alguém, essa senha é conhecida
    por duas pessoas. A obrigação de trocar existe para encurtar essa janela
    ao primeiro acesso — e **só vale se for verificada em toda requisição**.
    Aplicar o desvio apenas no instante do login deixa a marca ligada sem
    efeito: basta digitar outra URL depois do desvio para continuar navegando
    com a senha que o administrador conhece.

    ``precisa_trocar`` é chamada a cada requisição, tipicamente
    ``lambda: current_user.must_change_password``. Como em :func:`requer_login`,
    o Flask-Login não é importado aqui.

    **O próprio ``endpoint_troca`` é isento automaticamente**, junto de
    ``endpoints_isentos``. Depender de o consumidor lembrar de incluí-lo
    produziria um laço de redirecionamento na tela que existe para sair da
    situação — o erro mais fácil de cometer e o mais caro, porque tranca todo
    mundo para fora ao mesmo tempo.

    O consumidor ainda precisa isentar, por conta própria, **o logout** (sem
    ele a pessoa fica presa dentro do aplicativo, sem poder nem sair) e os
    endpoints de arquivo estático (sem eles a tela de troca chega sem CSS).

    Não carrega ``next``: quem chega aqui foi interrompido por uma obrigação,
    não barrado a caminho de um destino, e a tela de troca devolve ao início.
    Isso mantém fora deste contrato a superfície de redirecionamento aberto.

    Pode ser registrada antes ou depois de :func:`requer_login` — a checagem de
    ``esta_autenticado`` torna a ordem indiferente para o resultado. O lugar
    natural continua sendo depois, junto do resto do controle de acesso.

    Levanta ``RuntimeError`` se chamada mais de uma vez no mesmo app, pela
    mesma razão de :func:`requer_login`.
    """
    if app.extensions.get(_MARCA_TROCA_SENHA):
        raise RuntimeError(
            "requer_troca_de_senha já foi registrado neste app. Chamar de "
            "novo tornaria a primeira chamada silenciosamente vencedora para "
            "parte das rotas — corrija o app para chamar uma vez só."
        )
    app.extensions[_MARCA_TROCA_SENHA] = True

    isentos = endpoints_isentos | {endpoint_troca}

    @app.before_request
    def _requer_troca_de_senha() -> Response | None:
        if request.endpoint is None or request.endpoint in isentos:
            return None
        # Quem não entrou não tem senha a trocar: o assunto dele é o login, e
        # quem responde por isso é `requer_login`.
        if not esta_autenticado() or not precisa_trocar():
            return None

        if usar_hx_redirect and request.headers.get("HX-Request", "").lower() == "true":
            resposta = make_response("", 403)
            resposta.headers["HX-Redirect"] = url_for(endpoint_troca)
            return resposta

        # 403 e não 401: a sessão é válida e a identidade está estabelecida.
        # Um 401 diria "autentique-se de novo", e entrar de novo não resolve
        # nada aqui -- a mesma distinção que `requer_papel` faz.
        if prefixo_api and request.path.startswith(prefixo_api):
            return jsonify({chave_erro_api: mensagem_api}), 403

        return redirect(url_for(endpoint_troca))


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
