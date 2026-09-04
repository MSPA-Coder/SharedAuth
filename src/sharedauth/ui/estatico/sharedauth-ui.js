/* Confirmação e aviso — componentes comuns aos consumidores.
 *
 * Sem dependência de biblioteca ou template de framework.
 *
 * ------------------------------------------------------------------------
 * REGRA DE USO (não é estética, é o que faz a confirmação proteger)
 *
 *   operação irreversível pede confirmação; operação reversível NÃO pede.
 *
 * Confirmar tudo treina a pessoa a clicar "sim" sem ler, e aí a confirmação
 * deixa de proteger qualquer coisa. Antes de pôr `data-sa-confirmar` num
 * botão, pergunte se a pessoa consegue desfazer aquilo sozinha pela própria
 * interface. Se consegue, não confirme.
 *
 * ------------------------------------------------------------------------
 * MODAL PARA DECIDIR, TOAST PARA INFORMAR
 *
 * Antes da ação destrutiva: modal bloqueante, com ícone de severidade.
 * Depois da ação: toast com o MESMO ícone e as MESMAS cores, sem bloquear.
 * Sucesso some sozinho; erro fica até ser fechado -- quem precisa ler uma
 * mensagem de erro raramente consegue lê-la em quatro segundos.
 *
 * ------------------------------------------------------------------------
 * USO DECLARATIVO (o caso comum)
 *
 *   <button type="submit"
 *           data-sa-confirmar="Excluir apaga o extrato e não pode ser desfeito."
 *           data-sa-titulo="Excluir posição"
 *           data-sa-severidade="error">Excluir</button>
 *
 * Atributos aceitos:
 *   data-sa-confirmar   mensagem (obrigatório; é o que liga o componente)
 *   data-sa-titulo      título; padrão "Confirmar"
 *   data-sa-severidade  success | error | warning | info; padrão "error"
 *   data-sa-ok          texto do botão de confirmar; padrão "Confirmar"
 *   data-sa-cancelar    texto do botão de cancelar; padrão "Cancelar"
 *   data-sa-formulario  id do <form> a enviar, quando o botão está fora dele
 *
 * USO PROGRAMÁTICO (quando a decisão é condicional)
 *
 *   const ok = await window.sharedauth.confirmar({
 *     mensagem: `Isso apaga ${n} comprovante(s).`, severidade: "error"
 *   });
 *   if (!ok) return;
 *
 *   window.sharedauth.avisar({ mensagem: "Salvo.", severidade: "success" });
 *
 * ------------------------------------------------------------------------
 * TRÊS DECISÕES QUE PARECEM DETALHE E NÃO SÃO
 *
 * 1. LISTENER DELEGADO NO DOCUMENTO, não um por elemento. A delegação cobre
 *    elementos inseridos por `hx-swap` sem reinicialização.
 *
 * 2. FOCO INICIAL NO "CANCELAR", não no "Confirmar". Num diálogo que apaga
 *    dado, um Enter distraído tem de cancelar, não destruir.
 *
 * 3. NADA DE ESTILO INLINE. A CSP dos apps é `style-src 'self'` sem
 *    `unsafe-inline`: atributo `style=` é bloqueado pelo navegador. Todo
 *    estado visual aqui é classe CSS. Ícone é SVG construído no DOM -- não
 *    `<img src="data:...">`, que cairia no `img-src 'self'`; SVG no DOM não
 *    é requisição e não passa por `img-src`.
 *
 * DEGRADAÇÃO: se este arquivo não carregar, nada intercepta nada e os botões
 * voltam a enviar o formulário direto. Sem confirmação é ruim; um botão que
 * engole o clique em silêncio é pior.
 */

(function () {
  "use strict";

  if (window.sharedauth && window.sharedauth.confirmar) return; // idempotente

  var SEVERIDADES = ["success", "error", "warning", "info"];
  var PADRAO_SEVERIDADE = "error";
  var SEGUNDOS_TOAST = 6000;

  function severidadeValida(valor) {
    return SEVERIDADES.indexOf(valor) !== -1 ? valor : PADRAO_SEVERIDADE;
  }

  // -----------------------------------------------------------------------
  // Ícones
  //
  // Traçado, não preenchimento: herda `currentColor` e acompanha a cor da
  // severidade sem uma cópia do ícone por cor. `aria-hidden` porque o
  // significado já está no texto -- um leitor de tela anunciando "triângulo"
  // antes da mensagem só atrasa quem depende dele.
  // -----------------------------------------------------------------------
  var TRACOS = {
    success: ["M20 6L9 17l-5-5"],
    // Circulo com X, e nao o mesmo triangulo do `warning`: se as duas
    // severidades so diferem pela COR, quem nao distingue vermelho de ambar
    // nao distingue "atencao" de "perigo". Forma diferente resolve sem
    // depender de cor.
    error: ["M12 22a10 10 0 100-20 10 10 0 000 20z", "M15 9l-6 6", "M9 9l6 6"],
    warning: ["M12 9v4", "M12 17h.01", "M10.3 3.9L2 18a2 2 0 001.7 3h16.6a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"],
    info: ["M12 16v-4", "M12 8h.01", "M12 22a10 10 0 100-20 10 10 0 000 20z"],
  };

  function criarIcone(severidade) {
    var NS = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    svg.classList.add("sa-icone");
    (TRACOS[severidade] || TRACOS.info).forEach(function (d) {
      var path = document.createElementNS(NS, "path");
      path.setAttribute("d", d);
      svg.appendChild(path);
    });
    return svg;
  }

  // -----------------------------------------------------------------------
  // Modal
  // -----------------------------------------------------------------------
  var modal = null; // { fundo, caixa, icone, titulo, texto, ok, cancelar }
  var emAberto = null; // { resolver, gatilho }

  function montarModal() {
    if (modal) return modal;

    var fundo = document.createElement("div");
    fundo.className = "sa-modal-fundo";
    fundo.hidden = true;

    var caixa = document.createElement("div");
    caixa.className = "sa-modal";
    caixa.setAttribute("role", "dialog");
    caixa.setAttribute("aria-modal", "true");
    caixa.setAttribute("aria-labelledby", "sa-modal-titulo");
    caixa.setAttribute("aria-describedby", "sa-modal-texto");

    var cabecalho = document.createElement("div");
    cabecalho.className = "sa-modal-cabecalho";

    var icone = criarIcone(PADRAO_SEVERIDADE);

    var titulo = document.createElement("h2");
    titulo.className = "sa-modal-titulo";
    titulo.id = "sa-modal-titulo";

    cabecalho.appendChild(icone);
    cabecalho.appendChild(titulo);

    var texto = document.createElement("p");
    texto.className = "sa-modal-texto";
    texto.id = "sa-modal-texto";

    var acoes = document.createElement("div");
    acoes.className = "sa-modal-acoes";

    var cancelar = document.createElement("button");
    cancelar.type = "button";
    cancelar.className = "sa-botao sa-botao-neutro";

    var ok = document.createElement("button");
    ok.type = "button";
    ok.className = "sa-botao sa-botao-acao";

    acoes.appendChild(cancelar);
    acoes.appendChild(ok);

    caixa.appendChild(cabecalho);
    caixa.appendChild(texto);
    caixa.appendChild(acoes);
    fundo.appendChild(caixa);
    document.body.appendChild(fundo);

    ok.addEventListener("click", function () { fechar(true); });
    cancelar.addEventListener("click", function () { fechar(false); });
    // Clique no fundo cancela; clique dentro da caixa, não.
    fundo.addEventListener("click", function (ev) {
      if (ev.target === fundo) fechar(false);
    });

    modal = { fundo: fundo, caixa: caixa, icone: icone, titulo: titulo, texto: texto, ok: ok, cancelar: cancelar };
    return modal;
  }

  function focalizaveis() {
    if (!modal) return [];
    return Array.prototype.slice.call(
      modal.caixa.querySelectorAll("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")
    ).filter(function (el) { return !el.disabled && el.offsetParent !== null; });
  }

  // Foco preso: sem isto, o Tab passeia pela página atrás do diálogo. O
  // Prender o foco impede o Tab de alcançar a página atrás do diálogo.
  function aoTeclar(ev) {
    if (!emAberto) return;
    if (ev.key === "Escape") {
      ev.preventDefault();
      fechar(false);
      return;
    }
    if (ev.key !== "Tab") return;
    var itens = focalizaveis();
    if (!itens.length) return;
    var primeiro = itens[0];
    var ultimo = itens[itens.length - 1];
    if (ev.shiftKey && document.activeElement === primeiro) {
      ev.preventDefault();
      ultimo.focus();
    } else if (!ev.shiftKey && document.activeElement === ultimo) {
      ev.preventDefault();
      primeiro.focus();
    }
  }

  function fechar(resultado) {
    if (!emAberto) return;
    var pendente = emAberto;
    emAberto = null;
    modal.fundo.hidden = true;
    document.removeEventListener("keydown", aoTeclar, true);
    document.documentElement.classList.remove("sa-modal-aberto");
    // Foco volta para quem abriu. Sem isto a pessoa que navega por teclado
    // recomeça do topo da página a cada confirmação.
    if (pendente.gatilho && typeof pendente.gatilho.focus === "function") {
      pendente.gatilho.focus();
    }
    pendente.resolver(resultado);
  }

  function confirmar(opcoes) {
    opcoes = opcoes || {};
    // Uma confirmação já aberta não é substituída: a segunda chamada é
    // recusada em vez de deixar duas promessas presas para sempre.
    if (emAberto) return Promise.resolve(false);

    var m = montarModal();
    var severidade = severidadeValida(opcoes.severidade);

    m.titulo.textContent = opcoes.titulo || "Confirmar";
    m.texto.textContent = opcoes.mensagem || "";
    m.ok.textContent = opcoes.ok || "Confirmar";
    m.cancelar.textContent = opcoes.cancelar || "Cancelar";

    var novoIcone = criarIcone(severidade);
    m.icone.replaceWith(novoIcone);
    m.icone = novoIcone;

    SEVERIDADES.forEach(function (s) { m.caixa.classList.remove("sa-" + s); });
    m.caixa.classList.add("sa-" + severidade);

    m.fundo.hidden = false;
    document.documentElement.classList.add("sa-modal-aberto");
    document.addEventListener("keydown", aoTeclar, true);

    return new Promise(function (resolver) {
      emAberto = { resolver: resolver, gatilho: document.activeElement };
      // Ver decisão 2 no cabeçalho: o foco inicial é o CANCELAR.
      m.cancelar.focus();
    });
  }

  // -----------------------------------------------------------------------
  // Toast
  // -----------------------------------------------------------------------
  var pilha = null;

  function montarPilha() {
    if (pilha) return pilha;
    pilha = document.createElement("div");
    pilha.className = "sa-avisos";
    // `role=status` e não `alert`: a pilha é um container que existe desde o
    // início, e `alert` faria o leitor de tela reanunciar a região a cada
    // inserção. A urgência vai no aviso individual.
    pilha.setAttribute("role", "status");
    pilha.setAttribute("aria-live", "polite");
    document.body.appendChild(pilha);
    return pilha;
  }

  function avisar(opcoes) {
    opcoes = opcoes || {};
    var severidade = severidadeValida(opcoes.severidade === undefined ? "info" : opcoes.severidade);
    var mensagem = opcoes.mensagem || "";
    if (!mensagem) return;

    // Erro e atenção ficam até serem fechados; sucesso e informação somem.
    // Quem precisa ler um erro raramente o lê em seis segundos.
    var permanente = opcoes.permanente !== undefined
      ? !!opcoes.permanente
      : (severidade === "error" || severidade === "warning");

    var aviso = document.createElement("div");
    aviso.className = "sa-aviso sa-" + severidade;
    aviso.setAttribute("role", severidade === "error" || severidade === "warning" ? "alert" : "status");

    aviso.appendChild(criarIcone(severidade));

    var texto = document.createElement("span");
    texto.className = "sa-aviso-texto";
    texto.textContent = mensagem;
    aviso.appendChild(texto);

    var fecharBtn = document.createElement("button");
    fecharBtn.type = "button";
    fecharBtn.className = "sa-aviso-fechar";
    fecharBtn.setAttribute("aria-label", "Fechar aviso");
    fecharBtn.textContent = "×";
    fecharBtn.addEventListener("click", function () { aviso.remove(); });
    aviso.appendChild(fecharBtn);

    montarPilha().appendChild(aviso);

    if (!permanente) {
      window.setTimeout(function () { aviso.remove(); }, SEGUNDOS_TOAST);
    }
    return aviso;
  }

  // -----------------------------------------------------------------------
  // Ligação declarativa
  // -----------------------------------------------------------------------
  function opcoesDoElemento(el) {
    return {
      mensagem: el.getAttribute("data-sa-confirmar") || "",
      titulo: el.getAttribute("data-sa-titulo") || "Confirmar",
      severidade: el.getAttribute("data-sa-severidade") || PADRAO_SEVERIDADE,
      ok: el.getAttribute("data-sa-ok") || undefined,
      cancelar: el.getAttribute("data-sa-cancelar") || undefined,
    };
  }

  function formularioDe(el) {
    var id = el.getAttribute("data-sa-formulario");
    if (id) return document.getElementById(id);
    // `el.form` cobre o botão com atributo `form=`, que `closest` não pega.
    if (el.form) return el.form;
    return el.closest ? el.closest("form") : null;
  }

  var LIBERADO = "saLiberado";

  document.addEventListener(
    "click",
    function (ev) {
      var alvo = ev.target.closest ? ev.target.closest("[data-sa-confirmar]") : null;
      if (!alvo) return;
      if (alvo.dataset[LIBERADO] === "1") return; // segunda passagem, já confirmada

      ev.preventDefault();
      ev.stopPropagation();

      confirmar(opcoesDoElemento(alvo)).then(function (ok) {
        if (!ok) return;
        var form = formularioDe(alvo);
        if (form) {
          // `requestSubmit(alvo)` preserva o SUBMITTER -- name/value do botão
          // clicado chegam ao servidor, e a validação nativa do formulário
          // roda.
          if (typeof form.requestSubmit === "function") {
            form.requestSubmit(alvo.type === "submit" ? alvo : undefined);
          } else {
            form.submit();
          }
          return;
        }
        if (alvo.tagName === "A" && alvo.getAttribute("href")) {
          window.location.assign(alvo.getAttribute("href"));
          return;
        }
        // Nem formulário nem link: reemite o clique uma única vez, para o
        // handler do próprio app receber.
        alvo.dataset[LIBERADO] = "1";
        alvo.click();
        delete alvo.dataset[LIBERADO];
      });
    },
    true
  );

  // -----------------------------------------------------------------------
  // HTMX
  //
  // O HTMX cancela a requisição pelo RETORNO de `confirm()`, que é síncrono.
  // Com modal a decisão é assíncrona, então o caminho é `preventDefault()` no
  // evento `htmx:confirm` e `issueRequest()` depois -- sem isto, um
  // `hx-confirm` trocado por modal dispararia a requisição antes de a pessoa
  // responder.
  // -----------------------------------------------------------------------
  document.addEventListener("htmx:confirm", function (ev) {
    var pergunta = ev.detail && ev.detail.question;
    if (!pergunta) return; // sem `hx-confirm` no elemento: não é para nós
    ev.preventDefault();
    var elt = ev.detail.elt;
    confirmar({
      mensagem: pergunta,
      titulo: (elt && elt.getAttribute("data-sa-titulo")) || "Confirmar",
      severidade: (elt && elt.getAttribute("data-sa-severidade")) || PADRAO_SEVERIDADE,
    }).then(function (ok) {
      if (ok) ev.detail.issueRequest(true);
    });
  });

  // -----------------------------------------------------------------------
  // Ponte para mensagem vinda do servidor
  //
  // Um `[data-sa-avisos]` com JSON vira toast no carregamento. Atributo de
  // dado, não `<script>` inline: `script-src 'self'` bloquearia o segundo.
  //
  //   <div hidden data-sa-avisos='[{"mensagem":"Salvo.","severidade":"success"}]'></div>
  // -----------------------------------------------------------------------
  function lerAvisosDoServidor(raiz) {
    (raiz || document).querySelectorAll("[data-sa-avisos]").forEach(function (no) {
      var bruto = no.getAttribute("data-sa-avisos");
      no.removeAttribute("data-sa-avisos"); // não repetir num swap
      var lista;
      try {
        lista = JSON.parse(bruto);
      } catch (erro) {
        return; // JSON quebrado não pode derrubar a página
      }
      if (!Array.isArray(lista)) return;
      lista.forEach(function (item) {
        if (item && item.mensagem) avisar(item);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () { lerAvisosDoServidor(document); });
  document.addEventListener("htmx:afterSwap", function (ev) { lerAvisosDoServidor(ev.target); });

  window.sharedauth = window.sharedauth || {};
  window.sharedauth.confirmar = confirmar;
  window.sharedauth.avisar = avisar;
  window.sharedauth.SEVERIDADES = SEVERIDADES.slice();
})();
