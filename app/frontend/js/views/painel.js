// Tela Painel (#/painel) — GET /api/indicadores (operacional) e GET /api/indicadores/analiticos (Gold).
import { api, ApiError } from '../api.js';
import {
  el,
  anunciar,
  criarAviso,
  criarCarregando,
  criarErroCarregamento,
  criarListaDados,
  formatarDataHora,
  formatarDiaIso,
  formatarNumero,
  formatarPeriodo,
} from '../ui.js';
import { ORIGEM_DESCRICAO } from '../constants.js';
import { criarGraficoBarras, criarGraficoColunas, criarIndicadores } from '../components/charts.js';

export const titulo = 'Painel de indicadores';

const lista = (v) => (Array.isArray(v) ? v : []);

function secaoGrafico(grafico) {
  return el('div', { class: 'secao' }, grafico);
}

function montarOperacional(ind) {
  const cartoes = criarIndicadores([
    { rotulo: 'Total de denúncias', valor: ind.total },
    { rotulo: 'Possíveis buracos', valor: ind.possiveis_buracos },
    { rotulo: 'Análises inconclusivas', valor: ind.inconclusivas },
    { rotulo: 'Sem indício de buraco', valor: ind.nao_identificadas },
    { rotulo: 'Sem fotografia', valor: ind.sem_imagem },
  ]);
  const graficos = el(
    'div',
    { class: 'graficos' },
    secaoGrafico(
      criarGraficoBarras({
        titulo: 'Denúncias por tipo de obstáculo',
        nomeCategoria: 'Tipo de obstáculo',
        dados: lista(ind.por_categoria).map((d) => ({ rotulo: d.rotulo || d.chave, valor: d.total })),
      }),
    ),
    secaoGrafico(
      criarGraficoBarras({
        titulo: 'Denúncias por bairro',
        nomeCategoria: 'Bairro',
        dados: lista(ind.por_bairro).map((d) => ({ rotulo: d.rotulo || d.chave, valor: d.total })),
      }),
    ),
    secaoGrafico(
      criarGraficoBarras({
        titulo: 'Denúncias por status',
        nomeCategoria: 'Status',
        dados: lista(ind.por_status).map((d) => ({ rotulo: d.rotulo || d.chave, valor: d.total })),
      }),
    ),
    secaoGrafico(
      criarGraficoBarras({
        titulo: 'Resultado da triagem da foto',
        nomeCategoria: 'Resultado',
        dados: lista(ind.por_resultado_visao).map((d) => ({ rotulo: d.rotulo || d.chave || 'Sem fotografia', valor: d.total })),
        nota: 'Triagem automática: não é confirmação. Cada resultado passa por revisão humana.',
      }),
    ),
    secaoGrafico(
      criarGraficoBarras({
        titulo: 'Denúncias por origem',
        nomeCategoria: 'Origem',
        dados: lista(ind.por_origem).map((d) => ({ rotulo: ORIGEM_DESCRICAO[d.chave] || d.rotulo || d.chave, valor: d.total })),
      }),
    ),
    secaoGrafico(
      criarGraficoColunas({
        titulo: 'Denúncias registradas por dia',
        nomeCategoria: 'Data',
        dados: lista(ind.por_dia).map((d) => ({ rotulo: formatarDiaIso(d.data), rotuloCurto: formatarDiaIso(d.data, { curto: true }), valor: d.total })),
      }),
    ),
  );
  return [
    cartoes,
    el(
      'p',
      { class: 'texto-secundario' },
      `Dados em tempo real do banco operacional. Gerado em ${formatarDataHora(ind.gerado_em)}. ${ind.inclui_simulados ? 'Inclui dados SIMULADOS de demonstração.' : 'Somente dados reais (sem simulados).'}`,
    ),
    graficos,
  ];
}

const NOMES_QUALIDADE = {
  linhas_raw: 'Linhas na camada Raw',
  linhas_bronze: 'Linhas na camada Bronze',
  duplicatas_removidas: 'Duplicatas removidas',
  datas_invalidas: 'Datas inválidas',
  coordenadas_invalidas: 'Coordenadas inválidas',
  campos_obrigatorios_ausentes: 'Campos obrigatórios ausentes',
  percentual_registros_validos: 'Registros válidos (%)',
  linhas_silver: 'Linhas na camada Silver',
  duplicatas_negocio_removidas: 'Duplicatas de negócio removidas',
  registros_validos: 'Registros válidos (quantidade)',
};

function montarAnalitico(g) {
  if (!g || g.disponivel === false || !g.gerado_em) {
    return [
      criarAviso(
        'info',
        'Indicadores analíticos ainda não disponíveis',
        (g && g.mensagem) || 'O pipeline de dados ainda não publicou um resumo (camada Gold).',
        'Para gerar: execute o pipeline de dados da pasta 02-Big-Data-Architecture (execução local ou DAG do Airflow). Ele exporta as denúncias pela API, trata os dados nas camadas Raw → Bronze → Silver → Gold e publica o resultado no servidor. Depois, recarregue esta página.',
      ),
    ];
  }
  const qualidade = g.qualidade && typeof g.qualidade === 'object' ? g.qualidade : {};
  const paresQualidade = Object.entries(qualidade).map(([k, v]) => [
    NOMES_QUALIDADE[k] || k.replace(/_/g, ' '),
    k.startsWith('percentual') ? `${formatarNumero(v, 1)}%` : formatarNumero(v),
  ]);
  const fontes = lista(g.fontes);
  return [
    criarListaDados([
      ['Gerado em', formatarDataHora(g.gerado_em, { longa: true })],
      ['Execução', g.execucao_id ? el('span', { class: 'mono', text: String(g.execucao_id) }) : null],
      ['Dados simulados', g.inclui_simulados === undefined ? null : g.inclui_simulados ? 'Incluídos (demonstração)' : 'Não incluídos'],
    ]),
    el(
      'div',
      { class: 'grade grade--2' },
      el(
        'div',
        { class: 'secao' },
        el('h3', { text: 'Fontes de dados' }),
        fontes.length
          ? el(
              'div',
              { class: 'tabela-rolagem' },
              el(
                'table',
                {},
                el('caption', { class: 'sr-only', text: 'Fontes de dados usadas pelo pipeline' }),
                el('thead', {}, el('tr', {}, el('th', { scope: 'col', text: 'Fonte' }), el('th', { scope: 'col', class: 'num', text: 'Linhas' }))),
                el('tbody', {}, fontes.map((f) => el('tr', {}, el('th', { scope: 'row', text: String(f.nome ?? '') }), el('td', { class: 'num', text: formatarNumero(f.linhas) })))),
              ),
            )
          : el('p', { class: 'texto-secundario', text: 'Nenhuma fonte informada.' }),
      ),
      el(
        'div',
        { class: 'secao' },
        el('h3', { text: 'Qualidade dos registros' }),
        paresQualidade.length ? criarListaDados(paresQualidade) : el('p', { class: 'texto-secundario', text: 'Sem informações de qualidade.' }),
      ),
    ),
    el(
      'div',
      { class: 'graficos' },
      secaoGrafico(
        criarGraficoBarras({
          titulo: 'Pipeline: denúncias por bairro',
          nomeCategoria: 'Bairro',
          dados: lista(g.denuncias_por_bairro).map((d) => ({
            rotulo: d.bairro,
            valor: d.total,
            extras: d.possiveis_buracos !== undefined ? { 'Possíveis buracos': d.possiveis_buracos } : undefined,
          })),
        }),
      ),
      secaoGrafico(
        criarGraficoBarras({
          titulo: 'Pipeline: denúncias por categoria',
          nomeCategoria: 'Categoria',
          dados: lista(g.denuncias_por_categoria).map((d) => ({ rotulo: d.rotulo || d.categoria, valor: d.total })),
        }),
      ),
      secaoGrafico(
        criarGraficoColunas({
          titulo: 'Pipeline: denúncias por período',
          nomeCategoria: 'Período',
          dados: lista(g.denuncias_por_periodo).map((d) => ({ rotulo: formatarPeriodo(d.periodo), valor: d.total })),
        }),
      ),
      secaoGrafico(
        criarGraficoBarras({
          titulo: 'Pipeline: denúncias por status',
          nomeCategoria: 'Status',
          dados: lista(g.denuncias_por_status).map((d) => ({ rotulo: d.rotulo || d.status, valor: d.total })),
        }),
      ),
      secaoGrafico(
        criarGraficoBarras({
          titulo: 'Pipeline: resultado da triagem da foto',
          nomeCategoria: 'Resultado',
          dados: lista(g.resultado_visao).map((d) => ({ rotulo: d.rotulo || d.classificacao || 'Sem fotografia', valor: d.total })),
        }),
      ),
    ),
  ];
}

export function render({ container, signal }) {
  container.append(
    el(
      'div',
      { class: 'cabecalho-pagina' },
      el('h1', { tabindex: '-1', text: 'Painel de indicadores' }),
      el(
        'p',
        {},
        'Acompanhe quantas denúncias foram registradas, onde estão e o que a triagem automática encontrou. Todos os gráficos têm uma tabela de dados equivalente.',
      ),
    ),
  );

  // ---- operacional ----
  const chk = el('input', { type: 'checkbox', id: 'painel-simulados', name: 'incluir_simulados', checked: true });
  const areaOperacional = el('div', { class: 'pilha', id: 'painel-operacional' });
  container.append(
    el(
      'section',
      { 'aria-labelledby': 'titulo-operacional', class: 'pilha' },
      el('h2', { id: 'titulo-operacional', text: 'Indicadores operacionais (tempo real)' }),
      el('div', { class: 'campo-check' }, chk, el('label', { for: 'painel-simulados', text: 'Incluir dados simulados (demonstração)' })),
      areaOperacional,
    ),
  );

  async function carregarOperacional() {
    areaOperacional.setAttribute('aria-busy', 'true');
    areaOperacional.replaceChildren(criarCarregando('Carregando indicadores...'));
    try {
      const ind = await api.indicadores(chk.checked, signal);
      if (signal.aborted) return;
      areaOperacional.replaceChildren(...montarOperacional(ind));
      anunciar(`Indicadores atualizados: ${formatarNumero(ind.total)} denúncias.`);
    } catch (erro) {
      if (erro instanceof ApiError && erro.tipo === 'cancelado') return;
      areaOperacional.replaceChildren(criarErroCarregamento(erro, carregarOperacional, 'Não foi possível carregar os indicadores'));
    } finally {
      areaOperacional.removeAttribute('aria-busy');
    }
  }
  chk.addEventListener('change', carregarOperacional);

  // ---- analítico (Gold) ----
  const areaAnalitica = el('div', { class: 'pilha', id: 'painel-analitico' });
  container.append(
    el(
      'section',
      { 'aria-labelledby': 'titulo-analitico', class: 'pilha' },
      el('h2', { id: 'titulo-analitico', text: 'Indicadores analíticos (pipeline de dados — camada Gold)' }),
      el(
        'p',
        { class: 'texto-secundario' },
        'Resumo produzido pelo pipeline de dados a partir das denúncias e de uma base simulada. Pode estar defasado em relação aos indicadores em tempo real.',
      ),
      areaAnalitica,
    ),
  );

  async function carregarAnalitico() {
    areaAnalitica.setAttribute('aria-busy', 'true');
    areaAnalitica.replaceChildren(criarCarregando('Carregando indicadores analíticos...'));
    try {
      const g = await api.indicadoresAnaliticos(signal);
      if (signal.aborted) return;
      areaAnalitica.replaceChildren(...montarAnalitico(g));
    } catch (erro) {
      if (erro instanceof ApiError && erro.tipo === 'cancelado') return;
      areaAnalitica.replaceChildren(criarErroCarregamento(erro, carregarAnalitico, 'Não foi possível carregar os indicadores analíticos'));
    } finally {
      areaAnalitica.removeAttribute('aria-busy');
    }
  }

  carregarOperacional();
  carregarAnalitico();
}
