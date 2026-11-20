// AcessaCidade — roteador da SPA (rotas por hash, contrato seção 7).
import { el, focar, anunciar, lerPreferencia, salvarPreferencia } from './ui.js';
import { APP_NOME, CONTEXTO_TELA } from './constants.js';
import { carregarOpcoes } from './opcoes.js';

import * as inicio from './views/inicio.js';
import * as registrar from './views/registrar.js';
import * as detalhe from './views/detalhe.js';
import * as analise from './views/analise.js';
import * as consultar from './views/consultar.js';
import * as assistente from './views/assistente.js';
import * as painel from './views/painel.js';
import * as revisao from './views/revisao.js';
import * as sobre from './views/sobre.js';
import * as naoEncontrada from './views/nao-encontrada.js';

const ROTAS = [
  { padrao: /^\/$/, base: '/', modulo: inicio },
  { padrao: /^\/registrar$/, base: '/registrar', modulo: registrar },
  { padrao: /^\/denuncia\/([^/]+)$/, base: '/denuncia', modulo: detalhe, parametros: ['ref'] },
  { padrao: /^\/analise$/, base: '/analise', modulo: analise },
  { padrao: /^\/consultar$/, base: '/consultar', modulo: consultar },
  { padrao: /^\/assistente$/, base: '/assistente', modulo: assistente },
  { padrao: /^\/painel$/, base: '/painel', modulo: painel },
  { padrao: /^\/revisao$/, base: '/revisao', modulo: revisao },
  { padrao: /^\/sobre$/, base: '/sobre', modulo: sobre },
];

/** Lê "#/caminho?x=1" -> {caminho: "/caminho", consulta: URLSearchParams}. */
export function lerHash(hash = window.location.hash) {
  let bruto = hash.replace(/^#/, '');
  if (!bruto.startsWith('/')) bruto = `/${bruto}`;
  const [caminhoBruto, qs = ''] = bruto.split('?');
  let caminho = caminhoBruto.replace(/\/+$/, '') || '/';
  try {
    caminho = decodeURI(caminho);
  } catch {
    /* mantém o caminho original */
  }
  return { caminho, consulta: new URLSearchParams(qs) };
}

function encontrarRota(caminho) {
  for (const rota of ROTAS) {
    const m = rota.padrao.exec(caminho);
    if (m) {
      const params = {};
      (rota.parametros || []).forEach((nome, i) => {
        try {
          params[nome] = decodeURIComponent(m[i + 1]);
        } catch {
          params[nome] = m[i + 1];
        }
      });
      return { rota, params };
    }
  }
  return { rota: { base: null, modulo: naoEncontrada }, params: {} };
}

const principal = document.getElementById('conteudo');
const botaoAjuda = document.getElementById('botao-ajuda');
let controladorAtual = null;
let limpezaAtual = null;
let primeiraRenderizacao = true;

function atualizarNavegacao(base) {
  document.querySelectorAll('#menu-principal a[data-rota]').forEach((a) => {
    if (a.dataset.rota === base) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
}

function atualizarBotaoAjuda(base, params) {
  if (!botaoAjuda) return;
  if (base === '/assistente') {
    botaoAjuda.hidden = true;
    return;
  }
  botaoAjuda.hidden = false;
  const consulta = new URLSearchParams();
  consulta.set('contexto', CONTEXTO_TELA[base] || 'outra');
  if (base === '/denuncia' && params.ref) {
    consulta.set('protocolo', params.ref);
    consulta.set('modo', 'explicar_resultado');
  }
  if (base === '/registrar') consulta.set('modo', 'descricao');
  botaoAjuda.setAttribute('href', `#/assistente?${consulta.toString()}`);
}

export function definirTitulo(titulo) {
  document.title = titulo ? `${titulo} | ${APP_NOME}` : `${APP_NOME} — denúncias de acessibilidade em calçadas`;
}

async function renderizar() {
  const hash = window.location.hash;
  // Âncoras internas que não são rotas (ex.: "#conteudo") não trocam de tela.
  if (hash && !hash.startsWith('#/')) {
    const alvo = document.getElementById(decodeURIComponent(hash.slice(1)));
    if (alvo) {
      focar(alvo);
      return;
    }
  }

  const { caminho, consulta } = lerHash(hash);
  const { rota, params } = encontrarRota(caminho);

  if (controladorAtual) controladorAtual.abort();
  if (typeof limpezaAtual === 'function') {
    try {
      limpezaAtual();
    } catch {
      /* ignora */
    }
  }
  controladorAtual = new AbortController();
  limpezaAtual = null;

  fecharMenu();
  atualizarNavegacao(rota.base);
  atualizarBotaoAjuda(rota.base, params);

  const container = el('div', { class: 'pagina' });
  principal.replaceChildren(container);

  const ctx = {
    container,
    params,
    consulta,
    signal: controladorAtual.signal,
    definirTitulo,
    recarregar: () => renderizar(),
  };
  const modulo = rota.modulo;
  definirTitulo(typeof modulo.titulo === 'function' ? modulo.titulo(ctx) : modulo.titulo);

  try {
    const resultado = modulo.render(ctx);
    // a view desenha o <h1> de forma síncrona; os dados chegam depois
    if (!primeiraRenderizacao) {
      window.scrollTo(0, 0);
      const h1 = container.querySelector('h1');
      if (h1) focar(h1, { rolar: false });
      anunciar(`Página: ${document.title}`);
    }
    primeiraRenderizacao = false;
    const limpeza = await resultado;
    if (typeof limpeza === 'function') limpezaAtual = limpeza;
  } catch (erro) {
    if (controladorAtual.signal.aborted) return;
    // eslint-disable-next-line no-console
    console.error(erro);
    container.replaceChildren(
      el('h1', { tabindex: '-1', text: 'Algo deu errado' }),
      el('p', { text: 'Não foi possível exibir esta página. Recarregue a página ou volte para o início.' }),
      el('p', {}, el('a', { class: 'botao', href: '#/' }, 'Voltar para o início')),
    );
  }
}

// ---------------- menu móvel ----------------
const botaoMenu = document.getElementById('botao-menu');
const menu = document.getElementById('menu-principal');

function fecharMenu() {
  if (!menu || !botaoMenu) return;
  menu.classList.remove('aberto');
  botaoMenu.setAttribute('aria-expanded', 'false');
}

if (botaoMenu && menu) {
  botaoMenu.addEventListener('click', () => {
    const aberto = menu.classList.toggle('aberto');
    botaoMenu.setAttribute('aria-expanded', String(aberto));
    if (aberto) {
      const primeiro = menu.querySelector('a');
      if (primeiro) primeiro.focus();
    }
  });
  menu.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape' && menu.classList.contains('aberto')) {
      fecharMenu();
      botaoMenu.focus();
    }
  });
}

// ---------------- link "Pular para o conteúdo" ----------------
const linkPular = document.getElementById('link-pular');
if (linkPular) {
  linkPular.addEventListener('click', (ev) => {
    ev.preventDefault();
    const h1 = principal.querySelector('h1');
    focar(h1 || principal);
  });
}

// ---------------- tamanho do texto ----------------
const CHAVE_FONTE = 'acessacidade.fonteGrande';
const botaoFonte = document.getElementById('botao-fonte');
function aplicarFonte(grande) {
  document.documentElement.classList.toggle('fonte-grande', grande);
  if (botaoFonte) botaoFonte.setAttribute('aria-pressed', String(grande));
}
aplicarFonte(lerPreferencia(CHAVE_FONTE) === '1');
if (botaoFonte) {
  botaoFonte.addEventListener('click', () => {
    const grande = !document.documentElement.classList.contains('fonte-grande');
    aplicarFonte(grande);
    salvarPreferencia(CHAVE_FONTE, grande ? '1' : '0');
    anunciar(grande ? 'Texto maior ativado.' : 'Texto no tamanho padrão.');
  });
}

// ---------------- inicialização ----------------
window.addEventListener('hashchange', renderizar);
carregarOpcoes(); // pré-carrega as enumerações (com fallback)
if (!window.location.hash) {
  history.replaceState(null, '', '#/');
}
renderizar();
