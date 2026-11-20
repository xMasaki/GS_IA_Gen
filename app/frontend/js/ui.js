// Utilitários de interface. REGRA DE SEGURANÇA: todo texto vindo da API é inserido
// com textContent / createTextNode. Nunca usar innerHTML com dados externos.

const SVG_NS = 'http://www.w3.org/2000/svg';
const PROPRIEDADES = new Set(['value', 'checked', 'disabled', 'selected', 'multiple', 'readOnly', 'required']);

function anexarFilhos(elemento, filhos) {
  for (const filho of filhos.flat(Infinity)) {
    if (filho === null || filho === undefined || filho === false) continue;
    if (typeof filho === 'string' || typeof filho === 'number') {
      elemento.appendChild(document.createTextNode(String(filho)));
    } else {
      elemento.appendChild(filho);
    }
  }
}

function aplicarPropriedades(elemento, props) {
  for (const [chave, valor] of Object.entries(props || {})) {
    if (valor === null || valor === undefined || valor === false) continue;
    if (chave === 'class') {
      elemento.setAttribute('class', valor);
    } else if (chave === 'text') {
      elemento.textContent = String(valor);
    } else if (chave === 'on') {
      for (const [evento, fn] of Object.entries(valor)) elemento.addEventListener(evento, fn);
    } else if (chave === 'dataset') {
      for (const [k, v] of Object.entries(valor)) elemento.dataset[k] = String(v);
    } else if (chave === 'hidden') {
      elemento.hidden = true;
    } else if (chave === 'style') {
      throw new Error('Atributo style proibido pela CSP: use classes CSS.');
    } else if (chave.startsWith('on')) {
      throw new Error('Atributos on* são proibidos: use a opção "on".');
    } else if (PROPRIEDADES.has(chave)) {
      elemento[chave] = valor;
    } else {
      elemento.setAttribute(chave, valor === true ? '' : String(valor));
    }
  }
}

/** Cria um elemento HTML: el('p', {class: 'x'}, 'texto', outroElemento). */
export function el(tag, props = {}, ...filhos) {
  const elemento = document.createElement(tag);
  aplicarPropriedades(elemento, props);
  anexarFilhos(elemento, filhos);
  return elemento;
}

/** Cria um elemento SVG. */
export function svgEl(tag, props = {}, ...filhos) {
  const elemento = document.createElementNS(SVG_NS, tag);
  aplicarPropriedades(elemento, props);
  anexarFilhos(elemento, filhos);
  return elemento;
}

export function limpar(elemento) {
  while (elemento.firstChild) elemento.removeChild(elemento.firstChild);
}

export function substituir(elemento, ...filhos) {
  limpar(elemento);
  anexarFilhos(elemento, filhos);
}

let contadorIds = 0;
export function idUnico(prefixo = 'id') {
  contadorIds += 1;
  return `${prefixo}-${contadorIds}`;
}

/** Anuncia uma mensagem para leitores de tela (região aria-live global). */
export function anunciar(mensagem) {
  const regiao = document.getElementById('anuncio');
  if (!regiao) return;
  regiao.textContent = '';
  window.setTimeout(() => {
    regiao.textContent = mensagem;
  }, 60);
}

/** Move o foco para o elemento (tornando-o focável se necessário). */
export function focar(elemento, { rolar = true } = {}) {
  if (!elemento) return;
  if (!elemento.hasAttribute('tabindex') && !/^(A|BUTTON|INPUT|SELECT|TEXTAREA)$/.test(elemento.tagName)) {
    elemento.setAttribute('tabindex', '-1');
  }
  elemento.focus({ preventScroll: !rolar });
  if (rolar && typeof elemento.scrollIntoView === 'function') {
    const reduzir = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    elemento.scrollIntoView({ block: 'start', behavior: reduzir ? 'auto' : 'smooth' });
  }
}

// ---------------- formatação ----------------

const fmtDataHora = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
const fmtData = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short' });
const fmtDataLonga = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'long', timeStyle: 'short' });

function paraData(iso) {
  if (!iso) return null;
  const data = new Date(iso);
  return Number.isNaN(data.getTime()) ? null : data;
}

export function formatarDataHora(iso, { longa = false } = {}) {
  const data = paraData(iso);
  if (!data) return iso ? String(iso) : 'Não informado';
  return (longa ? fmtDataLonga : fmtDataHora).format(data);
}

export function formatarData(iso) {
  const data = paraData(iso);
  return data ? fmtData.format(data) : iso ? String(iso) : 'Não informado';
}

/** "2026-11-10" -> "10/11/2026" sem conversão de fuso. */
export function formatarDiaIso(texto, { curto = false } = {}) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(texto || ''));
  if (!m) return String(texto ?? '');
  return curto ? `${m[3]}/${m[2]}` : `${m[3]}/${m[2]}/${m[1]}`;
}

/** "2026-10" -> "10/2026"; outros formatos voltam como estão. */
export function formatarPeriodo(texto) {
  const m = /^(\d{4})-(\d{2})$/.exec(String(texto || ''));
  if (m) return `${m[2]}/${m[1]}`;
  return formatarDiaIso(texto);
}

export function formatarNumero(valor, casas = null) {
  if (valor === null || valor === undefined || valor === '') return '—';
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return String(valor);
  const opcoes = casas === null ? { maximumFractionDigits: 3 } : { minimumFractionDigits: casas, maximumFractionDigits: casas };
  return new Intl.NumberFormat('pt-BR', opcoes).format(numero);
}

export function truncar(texto, limite = 140) {
  const t = String(texto ?? '').replace(/\s+/g, ' ').trim();
  return t.length > limite ? `${t.slice(0, limite - 1).trimEnd()}…` : t;
}

export function formatarEndereco(d) {
  const partes = [];
  const rua = [d.logradouro, d.numero].filter(Boolean).join(', ');
  if (rua) partes.push(rua);
  if (d.bairro) partes.push(d.bairro);
  if (d.cidade) partes.push(d.cidade);
  return partes.join(' — ') || 'Endereço não informado';
}

export function formatarTamanhoArquivo(bytes) {
  if (!Number.isFinite(bytes)) return '';
  if (bytes < 1024 * 1024) return `${formatarNumero(bytes / 1024, 0)} KB`;
  return `${formatarNumero(bytes / (1024 * 1024), 1)} MB`;
}

// ---------------- componentes simples ----------------

export function criarCarregando(texto = 'Carregando...') {
  return el(
    'div',
    { class: 'carregando', role: 'status' },
    el('span', { class: 'carregando__indicador', 'aria-hidden': 'true' }),
    el('span', { text: texto }),
  );
}

/**
 * Caixa de aviso. tipo: info | alerta | erro | sucesso.
 * conteudo pode ser string ou elementos.
 */
export function criarAviso(tipo, titulo, ...conteudo) {
  const filhos = conteudo.flat().map((c) => (typeof c === 'string' ? el('p', { text: c }) : c));
  return el(
    'div',
    { class: `aviso aviso--${tipo}` },
    titulo ? el('p', { class: 'aviso__titulo' }, el('strong', { text: titulo })) : null,
    ...filhos,
  );
}

/** Mensagem de erro com botão "Tentar novamente" opcional. */
export function criarErroCarregamento(erro, aoTentarNovamente, titulo = 'Não foi possível carregar as informações') {
  const caixa = criarAviso('erro', titulo, erro && erro.message ? erro.message : 'Erro inesperado.');
  caixa.setAttribute('role', 'alert');
  if (aoTentarNovamente) {
    caixa.appendChild(
      el('button', { type: 'button', class: 'botao botao--secundario', on: { click: aoTentarNovamente } }, 'Tentar novamente'),
    );
  }
  return caixa;
}

export function criarSeloSimulado() {
  return el(
    'span',
    { class: 'selo selo--simulado', title: 'Dado fictício, usado apenas para demonstração' },
    'SIMULADO',
    el('span', { class: 'sr-only', text: ' (dado fictício de demonstração)' }),
  );
}

const ICONES_STATUS = {
  RECEBIDA: '●',
  EM_ANALISE: '◐',
  AGUARDANDO_REVISAO: '◷',
  ENCAMINHADA: '➜',
  RESOLVIDA: '✓',
};

export function criarSeloStatus(chave, rotulo) {
  const classe = ICONES_STATUS[chave] ? `selo--status-${chave}` : 'selo--neutro';
  return el(
    'span',
    { class: `selo ${classe}` },
    el('span', { class: 'selo__icone', 'aria-hidden': 'true', text: ICONES_STATUS[chave] || '●' }),
    el('span', { class: 'sr-only', text: 'Status: ' }),
    rotulo || chave || 'Desconhecido',
  );
}

const ICONES_VISAO = { POSSIBLE_POTHOLE: '!', NOT_IDENTIFIED: '○', INCONCLUSIVE: '?', SEM_FOTO: '–' };

export function criarSeloVisao(chave, rotulo) {
  const k = chave || 'SEM_FOTO';
  const classe = ICONES_VISAO[k] ? `selo--visao-${k}` : 'selo--neutro';
  return el(
    'span',
    { class: `selo ${classe}` },
    el('span', { class: 'selo__icone', 'aria-hidden': 'true', text: ICONES_VISAO[k] || '•' }),
    el('span', { class: 'sr-only', text: 'Triagem da foto: ' }),
    rotulo || k,
  );
}

/** Lista de definição a partir de pares [rótulo, valor]. Valores vazios são omitidos. */
export function criarListaDados(pares, classe = 'dados') {
  const dl = el('dl', { class: classe });
  for (const [rotulo, valor] of pares) {
    if (valor === null || valor === undefined || valor === '') continue;
    dl.appendChild(el('dt', { text: rotulo }));
    dl.appendChild(el('dd', {}, valor));
  }
  return dl;
}

/** Aceita apenas URLs de imagem da própria API ou data URIs de imagem (defesa extra). */
export function urlImagemSegura(url) {
  if (typeof url !== 'string') return null;
  if (/^data:image\/(jpeg|jpg|png|webp);base64,[A-Za-z0-9+/=\s]+$/.test(url)) return url;
  if (/^\/api\/[A-Za-z0-9/_.\-]+$/.test(url)) return url;
  return null;
}

/** Link interno para o detalhe de uma denúncia. */
export function hrefDenuncia(protocolo) {
  return `#/denuncia/${encodeURIComponent(protocolo)}`;
}

/** Lê/salva preferências locais com tolerância a falhas (modo privado etc.). */
export function lerPreferencia(chave, padrao = null) {
  try {
    const v = window.localStorage.getItem(chave);
    return v === null ? padrao : v;
  } catch {
    return padrao;
  }
}

export function salvarPreferencia(chave, valor) {
  try {
    window.localStorage.setItem(chave, valor);
  } catch {
    /* armazenamento indisponível: ignora */
  }
}
