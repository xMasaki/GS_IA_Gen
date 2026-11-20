// Renderização do resultado da triagem por visão computacional.
// Usado no detalhe da denúncia (imagens = URLs /api/...) e na tela de análise (data URIs).
import { el, svgEl, criarAviso, criarSeloVisao, formatarNumero, urlImagemSegura, idUnico } from '../ui.js';
import { AVISO_TRIAGEM, ETAPAS, LEGENDAS_ETAPAS, NOMES_METRICAS } from '../constants.js';
import { rotuloDe } from '../opcoes.js';

function nomeMetrica(chave) {
  if (NOMES_METRICAS[chave]) return NOMES_METRICAS[chave];
  const texto = String(chave).replace(/_/g, ' ');
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function valorMetrica(valor) {
  if (typeof valor === 'boolean') return valor ? 'Sim' : 'Não';
  if (typeof valor === 'number') return formatarNumero(valor);
  if (valor === null || valor === undefined) return '—';
  if (Array.isArray(valor)) {
    return valor.every((v) => typeof v !== 'object') ? valor.map((v) => (typeof v === 'number' ? formatarNumero(v) : String(v))).join('; ') : JSON.stringify(valor);
  }
  if (typeof valor === 'object') return JSON.stringify(valor);
  return String(valor);
}

/** Achata um nível de objetos aninhados: {a: {b: 1}} -> [["a / b", 1]]. */
function linhasMetricas(metricas) {
  const linhas = [];
  for (const [chave, valor] of Object.entries(metricas || {})) {
    if (valor && typeof valor === 'object' && !Array.isArray(valor)) {
      for (const [sub, v] of Object.entries(valor)) linhas.push([`${nomeMetrica(chave)} — ${nomeMetrica(sub)}`, v]);
    } else {
      linhas.push([nomeMetrica(chave), valor]);
    }
  }
  return linhas;
}

// Métricas mais úteis para quem lê o resultado (as demais ficam em "dados técnicos").
const METRICAS_PRINCIPAIS = [
  ['brilho_medio', (v) => `${formatarNumero(v)} (0 = preto, 255 = branco)`],
  ['contraste_rms', null],
  ['nitidez_laplaciano', null],
  ['percentual_pixels_escuros', (v) => `${formatarNumero(v)}%`],
  ['percentual_mascara', (v) => `${formatarNumero(v)}%`],
  ['densidade_bordas_global', null],
  ['num_candidatas', null],
  ['num_deteccoes', null],
  ['qualidade_adequada', null],
  ['problemas_qualidade', (v) => (Array.isArray(v) && v.length ? v.join('; ') : 'Nenhum')],
];

function linhasPrincipais(metricas) {
  const m = metricas || {};
  const linhas = [];
  if (typeof m.largura_original === 'number' && typeof m.altura_original === 'number') {
    linhas.push(['Tamanho da foto enviada', `${formatarNumero(m.largura_original)} × ${formatarNumero(m.altura_original)} px`]);
  }
  for (const [chave, formatar] of METRICAS_PRINCIPAIS) {
    if (!(chave in m)) continue;
    linhas.push([nomeMetrica(chave), formatar ? formatar(m[chave]) : valorMetrica(m[chave])]);
  }
  if (linhas.length) return linhas;
  // formato desconhecido: mostra apenas valores simples
  return Object.entries(m)
    .filter(([, v]) => v === null || typeof v !== 'object')
    .map(([chave, v]) => [nomeMetrica(chave), valorMetrica(v)]);
}

function criarTabelaMetricas(linhas, legenda, classeValor) {
  return el(
    'div',
    { class: 'tabela-rolagem', role: 'region', 'aria-label': legenda, tabindex: '0' },
    el(
      'table',
      { class: 'tabela-metricas' },
      el('caption', { class: 'sr-only', text: legenda }),
      el('thead', {}, el('tr', {}, el('th', { scope: 'col', text: 'Métrica' }), el('th', { scope: 'col', text: 'Valor' }))),
      el(
        'tbody',
        {},
        linhas.map(([nome, valor]) => el('tr', {}, el('th', { scope: 'row', text: nome }), el('td', { class: classeValor, text: String(valor) }))),
      ),
    ),
  );
}

function criarMedidorPontuacao(pontuacao) {
  const valor = Math.max(0, Math.min(1, Number(pontuacao) || 0));
  const pct = `${(valor * 100).toFixed(1)}%`;
  return svgEl(
    'svg',
    { 'aria-hidden': 'true', focusable: 'false', height: '16' },
    svgEl('rect', { class: 'pontuacao__trilha', x: '0.5', y: '0.5', width: '99%', height: '15', rx: '7' }),
    valor > 0 ? svgEl('rect', { class: 'pontuacao__barra', x: '0', y: '0', width: pct, height: '16', rx: '7' }) : null,
  );
}

function criarFiguraEtapa(etapa, url, indice) {
  const legenda = LEGENDAS_ETAPAS[etapa] || { titulo: etapa, texto: '' };
  const src = urlImagemSegura(url);
  const li = el('li', {});
  const idLegenda = idUnico(`legenda-${etapa}`);
  const conteudoImagem = src
    ? el('img', {
        src,
        alt: `Etapa ${indice + 1} da triagem: ${legenda.titulo}.`,
        loading: 'lazy',
        decoding: 'async',
        'aria-describedby': idLegenda,
      })
    : el('div', { class: 'etapa__indisponivel', text: 'Imagem desta etapa não disponível.' });

  const botaoAmpliar = src
    ? el(
        'button',
        {
          type: 'button',
          class: 'botao botao--secundario botao--compacto',
          'aria-pressed': 'false',
          on: {
            click: (ev) => {
              const ampliada = li.classList.toggle('ampliada');
              ev.currentTarget.setAttribute('aria-pressed', String(ampliada));
              ev.currentTarget.textContent = ampliada ? 'Reduzir imagem' : 'Ampliar imagem';
            },
          },
        },
        'Ampliar imagem',
      )
    : null;

  li.appendChild(
    el(
      'figure',
      { class: 'etapa' },
      conteudoImagem,
      el(
        'figcaption',
        { id: idLegenda },
        el('strong', { text: `${indice + 1}. ${legenda.titulo}` }),
        legenda.texto,
      ),
      botaoAmpliar,
    ),
  );
  return li;
}

/**
 * Renderiza o resultado da triagem.
 * @param {object} visao objeto `visao` (contrato 4.1) ou resposta de POST /api/visao/analisar (4.5)
 * @param {{nivel?: number}} opcoes nível dos títulos internos (padrão h3)
 */
export function renderizarAnaliseVisao(visao, { nivel = 3 } = {}) {
  const h = `h${nivel}`;
  const rotulo = visao.rotulo || rotuloDe('classificacao_visao', visao.classificacao);
  const pontuacao = Number(visao.pontuacao);
  const temPontuacao = Number.isFinite(pontuacao);
  const explicacoes = Array.isArray(visao.explicacao) ? visao.explicacao : visao.explicacao ? [String(visao.explicacao)] : [];
  const deteccoes = Array.isArray(visao.deteccoes) ? visao.deteccoes : [];
  const imagens = visao.imagens && typeof visao.imagens === 'object' ? visao.imagens : {};

  const raiz = el('div', { class: 'analise-visao' });

  // Aviso de triagem automática + revisão humana
  raiz.appendChild(
    criarAviso(
      'alerta',
      'Triagem automática — não é uma decisão',
      visao.aviso || AVISO_TRIAGEM,
      'O resultado serve apenas para ajudar a equipe a priorizar. Uma pessoa sempre pode revisar, confirmar ou descartar.',
    ),
  );

  // Resumo do resultado
  const blocoResultado = el(
    'div',
    {},
    el(h, { text: 'Resultado da triagem' }),
    el('p', {}, criarSeloVisao(visao.classificacao, rotulo)),
    visao.versao_algoritmo ? el('p', { class: 'texto-secundario', text: `Versão do algoritmo: ${visao.versao_algoritmo}` }) : null,
    el('p', { class: 'texto-secundario' }, `Regiões candidatas destacadas: ${deteccoes.length}.`),
  );
  const idExplicaPontuacao = idUnico('explica-pontuacao');
  const blocoPontuacao = el(
    'div',
    { class: 'pontuacao' },
    el(h, { text: 'Pontuação heurística' }),
    el(
      'p',
      { class: 'pontuacao__valor', 'aria-describedby': idExplicaPontuacao },
      temPontuacao ? `${formatarNumero(pontuacao, 2)} de 1` : 'Não informada',
    ),
    temPontuacao ? criarMedidorPontuacao(pontuacao) : null,
    el(
      'p',
      { id: idExplicaPontuacao, class: 'texto-secundario' },
      'Indica o quanto a foto combina com os sinais que o algoritmo procura (regiões escuras, bordas e formato). ',
      el('strong', { text: 'Não é uma probabilidade nem uma certeza' }),
      ' de que exista um buraco.',
    ),
  );
  raiz.appendChild(el('div', { class: 'analise-resumo' }, blocoResultado, blocoPontuacao));

  // Explicações
  raiz.appendChild(el(h, { text: 'Por que o algoritmo chegou a esse resultado' }));
  raiz.appendChild(
    explicacoes.length
      ? el('ul', {}, explicacoes.map((t) => el('li', { text: String(t) })))
      : el('p', { class: 'texto-secundario', text: 'O algoritmo não enviou explicações para esta análise.' }),
  );

  // Métricas
  raiz.appendChild(el(h, { text: 'Métricas principais' }));
  const principais = linhasPrincipais(visao.metricas);
  if (principais.length) {
    raiz.appendChild(criarTabelaMetricas(principais, 'Métricas principais calculadas pela triagem automática', 'metrica-valor'));
  } else {
    raiz.appendChild(el('p', { class: 'texto-secundario', text: 'Nenhuma métrica disponível.' }));
  }
  const todas = linhasMetricas(visao.metricas).map(([nome, valor]) => [nome, valorMetrica(valor)]);
  if (todas.length) {
    raiz.appendChild(
      el(
        'details',
        { class: 'detalhes-tecnicos' },
        el('summary', { text: `Ver todos os dados técnicos da análise (${todas.length} itens)` }),
        el('p', { class: 'texto-secundario', text: 'Valores internos do algoritmo, úteis para a equipe técnica. Coordenadas referem-se à imagem redimensionada para análise.' }),
        criarTabelaMetricas(todas, 'Todos os dados técnicos da triagem automática', 'metrica-valor metrica-valor--tecnico'),
      ),
    );
  }

  // Etapas
  raiz.appendChild(el(h, { text: 'Etapas do processamento da imagem' }));
  raiz.appendChild(
    el(
      'p',
      { class: 'texto-secundario' },
      'Veja, na ordem, como a foto é transformada até chegar ao resultado. Cada etapa tem uma explicação.',
    ),
  );
  const lista = el('ol', { class: 'etapas' });
  ETAPAS.forEach((etapa, i) => lista.appendChild(criarFiguraEtapa(etapa, imagens[etapa], i)));
  raiz.appendChild(lista);

  raiz.appendChild(
    el(
      'p',
      { class: 'texto-secundario' },
      'Limites: a triagem pode errar com sombras, manchas, folhas, piso escuro, pouca luz ou fotos tremidas. Por isso o resultado é sempre revisado por uma pessoa.',
    ),
  );
  return raiz;
}
