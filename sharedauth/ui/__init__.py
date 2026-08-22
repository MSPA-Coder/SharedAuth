"""Componentes de interface comuns para confirmação e aviso.

O módulo entrega CSS e JavaScript puros, além do caminho dos assets. Cada
framework mantém a responsabilidade de servir arquivos estáticos:

**Flask** -- ``registrar_ui(app)`` pendura um Blueprint que serve os arquivos
com ETag/304 de graça::

    from sharedauth.ui import registrar_ui
    registrar_ui(app)

    # no template:
    <link rel="stylesheet" href="{{ url_for('sharedauth_ui.static',
                                            filename='sharedauth-ui.css') }}">
    <script src="{{ url_for('sharedauth_ui.static',
                            filename='sharedauth-ui.js') }}" defer></script>

**Django** -- acrescenta :data:`CAMINHO_ESTATICO` com prefixo em
``STATICFILES_DIRS``, e o WhiteNoise cuida do resto (inclusive nome com hash)::

    from sharedauth.ui import CAMINHO_ESTATICO
    STATICFILES_DIRS = [..., ("sharedauth", CAMINHO_ESTATICO)]

    {% load static %}
    <link rel="stylesheet" href="{% static 'sharedauth/sharedauth-ui.css' %}">
    <script src="{% static 'sharedauth/sharedauth-ui.js' %}" defer></script>

O import do Flask é local a :func:`registrar_ui`; importar este módulo não
carrega Flask.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

#: Diretório com o CSS e o JS. É um ``Path`` de propósito: o Django quer um
#: caminho de sistema de arquivos em ``STATICFILES_DIRS``, não uma URL.
CAMINHO_ESTATICO: Path = Path(__file__).resolve().parent / "estatico"

ARQUIVO_CSS = "sharedauth-ui.css"
ARQUIVO_JS = "sharedauth-ui.js"

#: Severidades compatíveis com `flash()` e `django.contrib.messages`.
SEVERIDADES = ("success", "error", "warning", "info")

#: Traçado de cada ícone, por severidade.
#:
#: ESTE DADO EXISTE DUAS VEZES: aqui, para o banner renderizado no servidor, e
#: em ``estatico/sharedauth-ui.js``, para o modal e o toast montados no
#: navegador. O JS não pode importar Python, então a cópia é inevitável.
#:
#: ``tests/test_ui.py`` compara o traçado do JS com este dicionário para manter
#: as duas representações sincronizadas.
TRACOS_ICONE: dict[str, tuple[str, ...]] = {
    "success": ("M20 6L9 17l-5-5",),
    # Circulo com X, e nao o mesmo triangulo do `warning`: se as duas
    # severidades so diferem pela COR, quem nao distingue vermelho de ambar nao
    # distingue "atencao" de "perigo". Forma diferente resolve sem depender de
    # cor.
    "error": (
        "M12 22a10 10 0 100-20 10 10 0 000 20z",
        "M15 9l-6 6",
        "M9 9l6 6",
    ),
    "warning": (
        "M12 9v4",
        "M12 17h.01",
        "M10.3 3.9L2 18a2 2 0 001.7 3h16.6a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
    ),
    "info": ("M12 16v-4", "M12 8h.01", "M12 22a10 10 0 100-20 10 10 0 000 20z"),
}

_ATRIBUTOS_SVG = (
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
    'focusable="false" class="sa-icone"'
)


def svg_icone(severidade: str) -> str:
    """SVG embutido do ícone da severidade, para renderizar no servidor.

    Embutido no HTML, não ``<img src="data:...">``: SVG no documento não é
    requisição e não passa pelo ``img-src 'self'`` da CSP. Traço em
    ``currentColor``, então a cor vem da classe de severidade em volta.

    Severidade desconhecida cai em ``info``, como nos templates de mensagem,
    evitando quebrar a página por causa de um `flash()` com categoria própria.
    """
    tracos = TRACOS_ICONE.get(severidade, TRACOS_ICONE["info"])
    caminhos = "".join(f'<path d="{d}"/>' for d in tracos)
    return f"<svg {_ATRIBUTOS_SVG}>{caminhos}</svg>"


def registrar_icone_jinja(app: Flask) -> None:
    """Expõe :func:`svg_icone` como ``sharedauth_icone`` nos templates.

    Chamado tanto por :func:`registrar_ui` quanto por
    :func:`sharedauth.messages.registrar_mensagens`: o banner de mensagem usa o
    ícone e pode ser registrado sem o pacote de interface, então quem registrar
    primeiro resolve. ``setdefault`` deixa a segunda chamada inofensiva.
    """
    from markupsafe import Markup  # dependência do Jinja, já presente

    app.jinja_env.globals.setdefault(
        "sharedauth_icone", lambda severidade: Markup(svg_icone(severidade))
    )


_MARCA_REGISTRO = "sharedauth_ui_registrado"


def registrar_ui(app: Flask) -> None:
    """Serve o CSS e o JS deste pacote num app Flask.

    Chamar duas vezes é seguro: a segunda chamada não faz nada, em vez de
    derrubar o app com erro de blueprint duplicado. Mesmo padrão de
    :func:`sharedauth.messages.registrar_mensagens`.
    """
    from flask import Blueprint  # local: o Django não instala Flask

    registrar_icone_jinja(app)

    if app.extensions.get(_MARCA_REGISTRO):
        return
    app.extensions[_MARCA_REGISTRO] = True

    # Nome diferente do blueprint de `messages` (que se chama `sharedauth`):
    # dois blueprints com o mesmo nome no mesmo app é erro em tempo de
    # registro.
    app.register_blueprint(
        Blueprint(
            "sharedauth_ui",
            __name__,
            static_folder="estatico",
            static_url_path="/sharedauth/ui",
        )
    )


__all__ = [
    "ARQUIVO_CSS",
    "ARQUIVO_JS",
    "CAMINHO_ESTATICO",
    "SEVERIDADES",
    "TRACOS_ICONE",
    "registrar_icone_jinja",
    "registrar_ui",
    "svg_icone",
]
