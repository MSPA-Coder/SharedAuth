"""Rota de saúde com formato estável e sonda opcional de dependência.

Com uma sonda, a rota responde se o serviço está apto a atender requisições
dependentes; sem sonda, responde apenas pela vida do processo.
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
    levanta exceção se o serviço não está apto. Ausente, a rota vira apenas
    prova de vida do processo.

    ``limiter`` isenta a rota do rate limit global. **O retorno de
    ``limiter.exempt`` precisa ser reatribuído**: como ``RouteLimit.__call__``
    do Flask-Limiter, ele devolve uma função *nova* e envolvida; descartar o
    retorno deixa a isenção sem efeito; por isso a atribuição é explícita.
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
