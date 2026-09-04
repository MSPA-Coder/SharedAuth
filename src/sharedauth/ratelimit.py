"""Limite de tentativas de login com Flask-Limiter e política padrão."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

if TYPE_CHECKING:
    from flask import Flask

__all__ = [
    "LIMITE_LOGIN_PADRAO",
    "aplicar_limite",
    "iniciar_limiter",
    "isentar_limite",
]

LIMITE_LOGIN_PADRAO = "10 per minute"

_logger = logging.getLogger(__name__)


def _app_tem_proxyfix(app: Flask) -> bool:
    """Percorre a cadeia de middlewares WSGI do app em busca de ``ProxyFix``.

    Anda pelo atributo ``.app`` porque outro middleware pode estar registrado
    por cima — a ordem de registro em ``wsgi_app`` não é garantida ser a
    última.
    """
    try:
        from werkzeug.middleware.proxy_fix import ProxyFix
    except ImportError:  # pragma: no cover - Werkzeug é dependência do extra
        return False

    camada = app.wsgi_app
    vistas: set[int] = set()
    while camada is not None and id(camada) not in vistas:
        if isinstance(camada, ProxyFix):
            return True
        vistas.add(id(camada))
        camada = getattr(camada, "app", None)
    return False


def iniciar_limiter(
    app: Flask,
    *,
    limites_padrao: Iterable[str] | None = None,
    storage_uri: str | None = None,
    estrategia: str | None = None,
    habilitado: bool = True,
    key_func: Callable[[], str] | None = None,
) -> Limiter:
    """Cria e inicializa uma instância própria para ``app``.

    Deliberadamente **não** é um singleton de módulo: ``Limiter.init_app``
    reconstrói o *storage* compartilhado a cada chamada. Reaproveitar um
    singleton entre apps no mesmo processo pode apagar contadores existentes.
    Cada app recebe a sua própria instância.

    Os parâmetros opcionais existem para que um consumidor com política
    própria continue dentro deste contrato em vez de montar o seu ``Limiter``
    por fora — que foi o que aconteceu, e é como um app deixa de receber as
    correções feitas nos outros. A biblioteca não decide a política: ela recebe
    a do consumidor.

    ``habilitado=False`` desliga o enforcement e serve para suíte de teste que
    não é sobre rate limit. **Nunca em produção**: o limitador desligado não
    avisa, e a ausência de proteção só aparece quando alguém a procura.

    Os valores vão para o construtor do ``Limiter``, não para ``app.config``.
    A diferença importa: o que já estiver em ``RATELIMIT_*`` na configuração do
    app continua vencendo (é assim que o Flask-Limiter resolve os dois), então
    um consumidor que hoje configura por ``app.config`` não muda de
    comportamento ao adotar os parâmetros.

    ``key_func`` decide por qual chave o limite é contado; o padrão,
    ``get_remote_address``, é o endereço IP da conexão TCP. **Atrás de um
    proxy reverso sem ``ProxyFix`` registrado em ``app.wsgi_app``, esse
    endereço é sempre o do proxy** — todo o tráfego real cai no mesmo balde, e
    o limite por IP vira, na prática, um limite global. Quando não é passado
    ``key_func`` e há ``limites_padrao`` configurado, esta função emite um
    aviso de log se não encontrar ``ProxyFix`` na cadeia de middlewares — não
    é erro porque a aplicação pode estar atrás de outro mecanismo de extração
    de IP, mas o silêncio é exatamente como esse tipo de configuração perigosa
    passa despercebido.
    """
    if (
        key_func is None
        and limites_padrao is not None
        and habilitado
        and not _app_tem_proxyfix(app)
    ):
        _logger.warning(
            "iniciar_limiter: %s usa o IP remoto (get_remote_address) sem "
            "ProxyFix registrado em wsgi_app. Atrás de um proxy reverso, "
            "todo o tráfego cai no mesmo balde de limite. Registre "
            "werkzeug.middleware.proxy_fix.ProxyFix ou passe key_func.",
            app.name,
        )

    limiter = Limiter(
        key_func=key_func or get_remote_address,
        default_limits=list(limites_padrao) if limites_padrao is not None else None,
        storage_uri=storage_uri,
        strategy=estrategia,
        enabled=habilitado,
    )
    limiter.init_app(app)
    return limiter


def _resolver_endpoints(app: Flask, endpoint: str | Iterable[str]) -> tuple[str, ...]:
    nomes = (endpoint,) if isinstance(endpoint, str) else tuple(endpoint)
    if not nomes:
        raise ValueError("informe ao menos um endpoint.")

    ausentes = [nome for nome in nomes if nome not in app.view_functions]
    if ausentes:
        raise KeyError(
            "endpoint não registrado neste app: "
            f"{', '.join(sorted(ausentes))}. Chame depois de registrar o "
            "blueprint, e confira o prefixo do endpoint."
        )
    return nomes


def aplicar_limite(
    app: Flask,
    limiter: Limiter,
    endpoint: str | Iterable[str],
    limite: str,
    **opcoes: Any,
) -> None:
    """Aplica ``limite`` a rotas já registradas, religando ``view_functions``.

    **Esta função existe por causa de um erro específico, cometido três vezes
    em três aplicativos diferentes.** ``RouteLimit.__call__`` do Flask-Limiter
    devolve uma função *nova*, embrulhada; o enforcement roda dentro desse
    embrulho, quando a view é de fato chamada — não no ``before_request``
    genérico. Escrever

    ::

        limiter.limit("60 per minute")(app.view_functions[endpoint])   # ERRADO

    e descartar o retorno deixa o limite decorado e **nunca aplicado**: a
    requisição chega na view original, sem limite nenhum, e nada falha nem
    registra aviso. O sintoma só aparece quando alguém vai medir.

    Os três casos reais: o login do MegaSena sem limite, as três rotas de
    polling do ConfortoTermico rodando no default global de 20/min em vez do
    dedicado de 60/min (gerando 429 em produção), e a isenção do health do
    coletor sem efeito.

    Chamar depois de registrar o blueprint — um endpoint desconhecido levanta
    ``KeyError`` com o nome, em vez de falhar silenciosamente.

    ``opcoes`` vai direto para ``limiter.limit`` (por exemplo
    ``override_defaults=True``).
    """
    for nome in _resolver_endpoints(app, endpoint):
        app.view_functions[nome] = limiter.limit(limite, **opcoes)(
            app.view_functions[nome]
        )


def isentar_limite(
    app: Flask,
    limiter: Limiter,
    endpoint: str | Iterable[str],
) -> None:
    """Isenta rotas já registradas do limite global, religando as views.

    Mesma armadilha de :func:`aplicar_limite`: ``limiter.exempt`` também
    devolve uma função nova, e descartar o retorno deixa a isenção sem efeito.
    Foi o que fez a sonda do Docker do coletor do ConfortoTermico — uma
    requisição a cada 60s — consumir o orçamento do limite global de 20/min.

    Para a rota de saúde criada por :func:`sharedauth.health.registrar_health`
    não é preciso chamar aqui: passe ``limiter=`` para ela, que já faz a
    reatribuição corretamente.
    """
    for nome in _resolver_endpoints(app, endpoint):
        app.view_functions[nome] = limiter.exempt(app.view_functions[nome])
