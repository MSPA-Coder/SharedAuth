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

O ETag poupa o corpo da resposta, mas não a ida ao servidor: cada
carregamento de página confirma os dois arquivos e recebe dois 304. Para
trocar isso por cache local de verdade, ligue o prazo e use a URL versionada
-- os dois juntos, nunca o prazo sozinho::

    registrar_ui(app, max_age_segundos=UM_ANO_EM_SEGUNDOS)

    # no template:
    <link rel="stylesheet" href="{{ sharedauth_asset('sharedauth-ui.css') }}">
    <script src="{{ sharedauth_asset('sharedauth-ui.js') }}" defer></script>

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

#: Um ano, o teto que a RFC 2616 recomendava e que os navegadores tratam como
#: "para sempre". Só é seguro junto da URL versionada de :func:`url_do_asset`.
UM_ANO_EM_SEGUNDOS = 31_536_000


def url_do_asset(nome_arquivo: str) -> str:
    """URL do asset com a versão do pacote na query (``?v=0.13.0``).

    Existe para tornar ``max_age_segundos`` utilizável. Sem versão na URL, um
    ``Cache-Control`` longo é uma armadilha: o navegador de quem já visitou o
    aplicativo continua servindo o CSS antigo depois de o consumidor atualizar
    a tag, e não há como forçar a atualização a não ser esperar o prazo vencer.

    A versão do pacote é a chave certa **porque as tags deste repositório são
    imutáveis por contrato** (ver `AGENTS.md`): o conteúdo destes arquivos não
    muda sem a versão mudar junto, então uma URL versionada nunca aponta para
    dois conteúdos diferentes. O inverso -- uma versão nova sem mudança no
    asset -- custa um download de alguns kilobytes, uma vez por atualização.

    Disponível nos templates como ``sharedauth_asset`` depois de
    :func:`registrar_ui`::

        <link rel="stylesheet" href="{{ sharedauth_asset('sharedauth-ui.css') }}">
        <script src="{{ sharedauth_asset('sharedauth-ui.js') }}" defer></script>

    Exige contexto de requisição, como o ``url_for`` que ela embrulha.
    """
    from flask import url_for

    from .. import __version__

    return url_for("sharedauth_ui.static", filename=nome_arquivo, v=__version__)


def registrar_ui(app: Flask, *, max_age_segundos: int | None = None) -> None:
    """Serve o CSS e o JS deste pacote num app Flask.

    Chamar duas vezes é seguro: a segunda chamada não faz nada, em vez de
    derrubar o app com erro de blueprint duplicado. Mesmo padrão de
    :func:`sharedauth.messages.registrar_mensagens`.

    ``max_age_segundos`` define o ``Cache-Control`` destes arquivos. Omitido --
    o padrão, e o comportamento de todas as versões anteriores -- vale o do
    Flask, que hoje é ``no-cache``: o navegador guarda o arquivo mas confirma a
    validade a cada carregamento de página, e volta um 304. São duas idas ao
    servidor por página que não trazem byte nenhum de conteúdo.

    **Ligue junto com :func:`url_do_asset`, não sozinho.** Um prazo longo numa
    URL sem versão prende o navegador no arquivo antigo depois que o consumidor
    atualiza a tag. :data:`UM_ANO_EM_SEGUNDOS` é o valor usual quando a URL é
    versionada.

    O prazo vale só para o blueprint deste pacote; a configuração
    ``SEND_FILE_MAX_AGE_DEFAULT`` do app não é alterada, porque os estáticos do
    consumidor não são assunto desta biblioteca.
    """
    from flask import Blueprint  # local: o Django não instala Flask

    registrar_icone_jinja(app)
    app.jinja_env.globals.setdefault("sharedauth_asset", url_do_asset)

    if app.extensions.get(_MARCA_REGISTRO):
        return
    app.extensions[_MARCA_REGISTRO] = True

    class _BlueprintDeAssets(Blueprint):
        """Blueprint que decide o próprio ``max_age``.

        Definida aqui dentro porque herdar de ``Blueprint`` exige o Flask
        importado, e o módulo precisa continuar importável sem ele -- é a
        mesma razão de o ``import`` acima ser local.
        """

        def get_send_file_max_age(self, filename: str | None) -> int | None:
            if max_age_segundos is not None:
                return max_age_segundos
            return super().get_send_file_max_age(filename)

    # Nome diferente do blueprint de `messages` (que se chama `sharedauth`):
    # dois blueprints com o mesmo nome no mesmo app é erro em tempo de
    # registro.
    app.register_blueprint(
        _BlueprintDeAssets(
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
    "UM_ANO_EM_SEGUNDOS",
    "registrar_icone_jinja",
    "registrar_ui",
    "svg_icone",
    "url_do_asset",
]
