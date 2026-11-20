// Gráficos SVG acessíveis (sem bibliotecas). Cada gráfico tem <title>/<desc>,
// e uma TABELA de dados equivalente (visível sob demanda, sempre lida por leitores de tela).
// Larguras/posições usam atributos SVG em porcentagem: nada de style inline (CSP).
import { el, svgEl, formatarNumero, idUnico } from '../ui.js';

const ALTURA_LINHA = 50;
const ESPESSURA_BARRA = 20; // <= 24px
const ESCALA_MAX = 78; // % da largura usada pela maior barra (deixa espaço para o valor)

function criarTabela({ titulo, nomeCategoria, nomeValor, dados }) {
  const extras = [];
  for (const d of dados) for (const k of Object.keys(d.extras || {})) if (!extras.includes(k)) extras.push(k);
  return el(
    'table',
    {},
    el('caption', { text: `Dados: ${titulo}` }),
    el(
      'thead',
      {},
      el(
        'tr',
        {},
        el('th', { scope: 'col', text: nomeCategoria }),
        el('th', { scope: 'col', class: 'num', text: nomeValor }),
        extras.map((k) => el('th', { scope: 'col', class: 'num', text: k })),
      ),
    ),
    el(
      'tbody',
      {},
      dados.map((d) =>
        el(
          'tr',
          {},
          el('th', { scope: 'row', text: d.rotulo }),
          el('td', { class: 'num', text: formatarNumero(d.valor) }),
          extras.map((k) => el('td', { class: 'num', text: formatarNumero(d.extras?.[k]) })),
        ),
      ),
    ),
  );
}

function montarFigura({ titulo, svg, tabela, nota }) {
  const idTabela = idUnico('tabela-grafico');
  const caixaTabela = el('div', { id: idTabela, class: 'grafico__tabela tabela-rolagem sr-only' }, tabela);
  const botao = el(
    'button',
    {
      type: 'button',
      class: 'botao botao--link',
      'aria-expanded': 'false',
      'aria-controls': idTabela,
      on: {
        click: () => {
          const aberto = caixaTabela.classList.toggle('sr-only') === false;
          botao.setAttribute('aria-expanded', String(aberto));
          botao.textContent = aberto ? 'Ocultar tabela de dados' : 'Mostrar tabela de dados';
        },
      },
    },
    'Mostrar tabela de dados',
  );
  return el(
    'figure',
    { class: 'grafico' },
    el('figcaption', { class: 'grafico__titulo', text: titulo }),
    svg,
    nota ? el('p', { class: 'grafico__nota', text: nota }) : null,
    el('div', {}, botao),
    caixaTabela,
  );
}

function descricaoTexto(dados, nomeValor) {
  const total = dados.reduce((s, d) => s + (Number(d.valor) || 0), 0);
  const ordenados = [...dados].sort((a, b) => (Number(b.valor) || 0) - (Number(a.valor) || 0));
  const top = ordenados.slice(0, 3).map((d) => `${d.rotulo}: ${formatarNumero(d.valor)}`).join('; ');
  return `${dados.length} ${dados.length === 1 ? 'item' : 'itens'}, soma de ${formatarNumero(total)} (${nomeValor.toLowerCase()}). Maiores valores: ${top}. A tabela de dados a seguir traz todos os valores.`;
}

/**
 * Barras horizontais.
 * @param {{titulo: string, dados: Array<{rotulo: string, valor: number, extras?: object}>, nomeCategoria?: string, nomeValor?: string, limite?: number, nota?: string}} cfg
 */
export function criarGraficoBarras({ titulo, dados, nomeCategoria = 'Categoria', nomeValor = 'Total', limite = 12, nota }) {
  const lista = (dados || []).filter((d) => d && d.rotulo !== undefined).map((d) => ({ ...d, rotulo: String(d.rotulo || 'Não informado'), valor: Number(d.valor) || 0 }));
  if (!lista.length) {
    return el('figure', { class: 'grafico' }, el('figcaption', { class: 'grafico__titulo', text: titulo }), el('p', { class: 'grafico__vazio', text: 'Sem dados para exibir.' }));
  }
  const ordenados = [...lista].sort((a, b) => b.valor - a.valor);
  const visiveis = ordenados.slice(0, limite);
  const maximo = Math.max(...visiveis.map((d) => d.valor), 1);
  const altura = visiveis.length * ALTURA_LINHA + 4;
  const idTitulo = idUnico('svg-titulo');
  const idDesc = idUnico('svg-desc');

  const svg = svgEl(
    'svg',
    { role: 'img', 'aria-labelledby': `${idTitulo} ${idDesc}`, height: String(altura), focusable: 'false' },
    svgEl('title', { id: idTitulo, text: titulo }),
    svgEl('desc', { id: idDesc, text: descricaoTexto(lista, nomeValor) }),
  );
  visiveis.forEach((d, i) => {
    const y0 = i * ALTURA_LINHA;
    const pct = (d.valor / maximo) * ESCALA_MAX;
    const grupo = svgEl('g', {}, svgEl('title', { text: `${d.rotulo}: ${formatarNumero(d.valor)}` }));
    grupo.appendChild(svgEl('text', { class: 'grafico__rotulo', x: '0', y: String(y0 + 15), text: d.rotulo }));
    if (d.valor > 0) {
      grupo.appendChild(
        svgEl('rect', { class: 'grafico__barra', x: '0', y: String(y0 + 22), width: `${pct.toFixed(2)}%`, height: String(ESPESSURA_BARRA), rx: '4' }),
      );
      // canto reto junto à linha de base
      grupo.appendChild(svgEl('rect', { class: 'grafico__barra', x: '0', y: String(y0 + 22), width: '4', height: String(ESPESSURA_BARRA) }));
    }
    grupo.appendChild(
      svgEl('text', { class: 'grafico__valor', x: `${pct.toFixed(2)}%`, dx: d.valor > 0 ? '8' : '2', y: String(y0 + 37), text: formatarNumero(d.valor) }),
    );
    svg.appendChild(grupo);
  });
  svg.appendChild(svgEl('line', { class: 'grafico__linha-base', x1: '0.5', x2: '0.5', y1: '18', y2: String(altura) }));

  const notaFinal = [nota, lista.length > visiveis.length ? `Mostrando os ${visiveis.length} maiores de ${lista.length}; a tabela traz todos.` : null]
    .filter(Boolean)
    .join(' ');
  return montarFigura({ titulo, svg, tabela: criarTabela({ titulo, nomeCategoria, nomeValor, dados: ordenados }), nota: notaFinal || null });
}

/**
 * Colunas verticais (séries temporais: por dia / por período). Mantém a ordem recebida.
 * @param {{titulo: string, dados: Array<{rotulo: string, rotuloCurto?: string, valor: number}>, nomeCategoria?: string, nomeValor?: string, nota?: string}} cfg
 */
export function criarGraficoColunas({ titulo, dados, nomeCategoria = 'Data', nomeValor = 'Total', nota }) {
  const lista = (dados || []).map((d) => ({ ...d, valor: Number(d.valor) || 0 }));
  if (!lista.length) {
    return el('figure', { class: 'grafico' }, el('figcaption', { class: 'grafico__titulo', text: titulo }), el('p', { class: 'grafico__vazio', text: 'Sem dados para exibir.' }));
  }
  const ALTURA = 210;
  const TOPO = 24;
  const BASE = 176;
  const maximo = Math.max(...lista.map((d) => d.valor), 1);
  const n = lista.length;
  const faixa = 100 / n;
  const passoRotulo = Math.max(1, Math.ceil(n / 7));
  const indiceMax = lista.findIndex((d) => d.valor === maximo);
  const idTitulo = idUnico('svg-titulo');
  const idDesc = idUnico('svg-desc');

  const svg = svgEl(
    'svg',
    { role: 'img', 'aria-labelledby': `${idTitulo} ${idDesc}`, height: String(ALTURA), focusable: 'false' },
    svgEl('title', { id: idTitulo, text: titulo }),
    svgEl(
      'desc',
      { id: idDesc, text: `Série com ${n} pontos, de ${lista[0].rotulo} a ${lista[n - 1].rotulo}. Maior valor: ${formatarNumero(maximo)} em ${lista[indiceMax].rotulo}. A tabela de dados a seguir traz todos os valores.` },
    ),
    svgEl('line', { class: 'grafico__grade', x1: '0', x2: '100%', y1: String(TOPO), y2: String(TOPO) }),
    svgEl('text', { class: 'grafico__eixo', x: '0', y: String(TOPO - 6), text: `máx. ${formatarNumero(maximo)}` }),
  );
  lista.forEach((d, i) => {
    const alturaColuna = ((BASE - TOPO) * d.valor) / maximo;
    const largura = Math.min(faixa * 0.7, 6); // no máximo ~6% da largura
    const x = i * faixa + (faixa - largura) / 2;
    const centro = i * faixa + faixa / 2;
    const grupo = svgEl('g', {}, svgEl('title', { text: `${d.rotulo}: ${formatarNumero(d.valor)}` }));
    if (d.valor > 0) {
      grupo.appendChild(
        svgEl('rect', { class: 'grafico__barra', x: `${x.toFixed(3)}%`, y: String(BASE - alturaColuna), width: `${largura.toFixed(3)}%`, height: String(alturaColuna), rx: '3' }),
      );
      grupo.appendChild(
        svgEl('rect', { class: 'grafico__barra', x: `${x.toFixed(3)}%`, y: String(BASE - Math.min(3, alturaColuna)), width: `${largura.toFixed(3)}%`, height: String(Math.min(3, alturaColuna)) }),
      );
    }
    if (i === indiceMax || i === n - 1) {
      grupo.appendChild(
        svgEl('text', { class: 'grafico__valor', x: `${centro.toFixed(3)}%`, y: String(BASE - alturaColuna - 6), 'text-anchor': 'middle', text: formatarNumero(d.valor) }),
      );
    }
    const mostrarRotulo = i % passoRotulo === 0 || (i === n - 1 && (n - 1) % passoRotulo >= Math.ceil(passoRotulo / 2));
    if (mostrarRotulo) {
      grupo.appendChild(
        svgEl('text', { class: 'grafico__eixo', x: `${centro.toFixed(3)}%`, y: String(BASE + 20), 'text-anchor': 'middle', text: d.rotuloCurto || d.rotulo }),
      );
    }
    svg.appendChild(grupo);
  });
  svg.appendChild(svgEl('line', { class: 'grafico__linha-base', x1: '0', x2: '100%', y1: String(BASE + 0.5), y2: String(BASE + 0.5) }));
  return montarFigura({ titulo, svg, tabela: criarTabela({ titulo, nomeCategoria, nomeValor, dados: lista }), nota });
}

/** Cartões de indicadores numéricos. itens: [{rotulo, valor}] */
export function criarIndicadores(itens) {
  return el(
    'ul',
    { class: 'indicadores' },
    itens.map((i) =>
      el(
        'li',
        {},
        el('div', { class: 'indicador' }, el('span', { class: 'indicador__rotulo', text: i.rotulo }), el('span', { class: 'indicador__valor', text: formatarNumero(i.valor) })),
      ),
    ),
  );
}
