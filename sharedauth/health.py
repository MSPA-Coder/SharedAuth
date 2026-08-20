"""Rota de saúde — mesma rota, mesmo formato, mesma pergunta nos três apps.

O levantamento que originou este módulo achou um defeito real, não só uma
inconsistência de forma: o MegaSena não tinha rota de saúde nenhuma, e o
`healthcheck:` do `compose.yaml` dele batia na raiz do site. Na prática o
Docker considerava o container saudável enquanto a tela de login carregasse —
inclusive com o banco fora do ar, que é justamente a situação que o health
check existe para detectar.

A pergunta que esta rota responde é "o serviço consegue atender uma
requisição que depende do banco?", não "o processo está de pé?". A segunda o
Docker já sabe sozinho.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - só para tipagem
    from flask import Blueprint, Flask


def registrar_health(
    alvo: Flask | Blueprint,
    *,
    servico: str,
    verificar: Callable[[], Any] | None = None,
    url: str = "/health",
    endpoint: str = "health",
    limiter: Any | None = None,
) -> Callable[[], Any]:
    """Registra ``GET /health`` e devolve a view registrada.

    ``verificar`` é a sonda de dependência: uma função sem argumentos que
    levanta exceção se o serviço não está apto. Nos três apps ela é uma
    consulta trivial ao banco (``db.session.execute(select(1))``). Ausente, a
    rota vira só prova de vida do processo — aceitável para um app sem banco,
    não para nenhum dos três.

    ``limiter`` isenta a rota do rate limit global. **O retorno de
    ``limiter.exempt`` precisa ser reatribuído**: como ``RouteLimit.__call__``
    do Flask-Limiter, ele devolve uma função *nova* e envolvida; descartar o
    retorno deixa a isenção decorada e nunca aplicada. Foi exatamente esse
    descuido que deixou o limite de login do MegaSena e três rotas de polling
    do ConfortoTermico inertes em produção — aqui a atribuição é explícita
    para o mesmo erro não voltar por uma terceira porta.
    """
    from flask import jsonify

    def health():
        if verificar is not None:
            try:
                verificar()
            except Exception:  # noqa: BLE001 - qualquer falha é "não apto"
                # Sem `logger.exception` aqui: quem chama tem o logger do app
                # e sabe o nome certo do serviço. Este módulo não decide
                # política de log de ninguém.
                return jsonify(servico=servico, status="erro"), 503
        return jsonify(servico=servico, status="ok")

    view: Callable[[], Any] = health
    if limiter is not None:
        view = limiter.exempt(view)

    alvo.add_url_rule(url, endpoint=endpoint, view_func=view, methods=["GET"])
    return view
