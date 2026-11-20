// Tela Detalhe da denúncia (#/denuncia/{protocolo})
import { api, ApiError } from '../api.js';
import {
  el,
  criarAviso,
  criarCarregando,
  criarErroCarregamento,
  criarListaDados,
  criarSeloSimulado,
  criarSeloStatus,
  formatarDataHora,
  formatarEndereco,
  formatarNumero,
} from '../ui.js';
import { ORIGEM_DESCRICAO, PROTOCOLO_REGEX, REVISAO_DESCRICAO } from '../constants.js';
import { rotuloDe, significadoStatus, carregarOpcoes } from '../opcoes.js';
import { renderizarAnaliseVisao } from '../components/vision-analysis.js';

export function titulo({ params }) {
  return `Denúncia ${params.ref || ''}`.trim();
}

function referenciaValida(ref) {
  return PROTOCOLO_REGEX.test(ref) || /^\d{1,9}$/.test(ref);
}

function criarHistorico(historico) {
  if (!Array.isArray(historico) || !historico.length) {
    return el('p', { class: 'texto-secundario', text: 'Nenhum registro de histórico.' });
  }
  return el(
    'ol',
    { class: 'linha-tempo' },
    historico.map((h) =>
      el(
        'li',
        {},
        el('span', { class: 'linha-tempo__data' }, el('time', { datetime: h.alterado_em || '', text: formatarDataHora(h.alterado_em) })),
        criarSeloStatus(h.status, h.status_rotulo || rotuloDe('status', h.status)),
        h.observacao ? el('p', { class: 'linha-tempo__obs', text: h.observacao }) : null,
      ),
    ),
  );
}

export function render({ container, params, signal, definirTitulo }) {
  const ref = String(params.ref || '').trim().toUpperCase();
  const h1 = el('h1', { tabindex: '-1', text: `Denúncia ${ref}` });
  container.append(el('div', { class: 'cabecalho-pagina' }, h1, el('p', {}, el('a', { href: '#/consultar', text: '← Voltar para a consulta' }))));

  if (!referenciaValida(ref)) {
    h1.textContent = 'Protocolo inválido';
    definirTitulo('Protocolo inválido');
    container.append(
      criarAviso(
        'erro',
        'Este endereço não tem um protocolo válido',
        'O protocolo tem o formato AC-2026-000012 (as letras AC, o ano e seis números).',
        el('p', {}, el('a', { class: 'botao', href: '#/consultar' }, 'Buscar uma denúncia')),
      ),
    );
    return;
  }

  const area = el('div', { class: 'pilha', 'aria-busy': 'true' }, criarCarregando('Carregando a denúncia...'));
  container.append(area);

  async function carregar() {
    area.setAttribute('aria-busy', 'true');
    area.replaceChildren(criarCarregando('Carregando a denúncia...'));
    try {
      await carregarOpcoes();
      const d = await api.obterDenuncia(ref, signal);
      if (signal.aborted) return;
      area.removeAttribute('aria-busy');
      montar(d);
    } catch (erro) {
      if (erro instanceof ApiError && erro.tipo === 'cancelado') return;
      area.removeAttribute('aria-busy');
      if (erro instanceof ApiError && erro.status === 404) {
        h1.textContent = 'Denúncia não encontrada';
        definirTitulo('Denúncia não encontrada');
        area.replaceChildren(
          criarAviso(
            'erro',
            `Não encontramos a denúncia ${ref}`,
            'Confira se o protocolo foi digitado corretamente (formato AC-2026-000012).',
            el('p', {}, el('a', { class: 'botao', href: '#/consultar' }, 'Buscar outra denúncia')),
          ),
        );
        return;
      }
      area.replaceChildren(criarErroCarregamento(erro, carregar, 'Não foi possível carregar a denúncia'));
    }
  }

  function montar(d) {
    h1.textContent = `Denúncia ${d.protocolo}`;
    definirTitulo(`Denúncia ${d.protocolo}`);
    const significado = significadoStatus(d.status);
    const coordenadas =
      d.latitude !== null && d.latitude !== undefined && d.longitude !== null && d.longitude !== undefined
        ? `${formatarNumero(d.latitude, 6)}, ${formatarNumero(d.longitude, 6)}`
        : 'Não informada';

    const secaoStatus = el(
      'section',
      { class: 'secao secao--destaque', 'aria-labelledby': 'titulo-status' },
      el('h2', { id: 'titulo-status', text: 'Situação atual' }),
      el('div', { class: 'selos' }, criarSeloStatus(d.status, d.status_rotulo || rotuloDe('status', d.status)), d.simulado ? criarSeloSimulado() : null),
      significado ? el('p', { text: significado }) : null,
      d.status === 'RESOLVIDA'
        ? el('p', { class: 'texto-secundario', text: '"Resolvida" é um registro da equipe do AcessaCidade, não uma confirmação de órgão público.' })
        : null,
      d.simulado
        ? el('p', { class: 'texto-secundario', text: 'Esta denúncia é SIMULADA: um dado fictício usado apenas para demonstração.' })
        : null,
    );

    const secaoDados = el(
      'section',
      { class: 'secao', 'aria-labelledby': 'titulo-dados' },
      el('h2', { id: 'titulo-dados', text: 'Dados da denúncia' }),
      criarListaDados([
        ['Protocolo', el('span', { class: 'mono', text: d.protocolo })],
        ['Registrada em', formatarDataHora(d.criado_em, { longa: true })],
        ['Última atualização', formatarDataHora(d.atualizado_em, { longa: true })],
        ['Endereço', formatarEndereco(d)],
        ['Ponto de referência', d.ponto_referencia || 'Não informado'],
        ['Localização (lat., long.)', coordenadas],
        ['Tipo de obstáculo', d.tipo_obstaculo_rotulo || rotuloDe('tipo_obstaculo', d.tipo_obstaculo)],
        ['Impacto', d.impacto_rotulo || rotuloDe('impacto', d.impacto)],
        ['Descrição', d.descricao],
        ['Origem do registro', ORIGEM_DESCRICAO[d.origem] || d.origem],
        ['Fotografia', d.possui_imagem ? 'Sim' : 'Não'],
        ['Revisão humana da triagem', d.revisao_humana ? REVISAO_DESCRICAO[d.revisao_humana] || d.revisao_humana : 'Ainda não revisada por uma pessoa.'],
      ]),
      el('p', { class: 'texto-secundario', text: 'O nome de quem registrou nunca é exibido.' }),
    );

    const secaoHistorico = el(
      'section',
      { class: 'secao', 'aria-labelledby': 'titulo-historico' },
      el('h2', { id: 'titulo-historico', text: 'Histórico' }),
      criarHistorico(d.historico),
    );

    const secaoAnalise = el(
      'section',
      { class: 'secao', 'aria-labelledby': 'titulo-analise' },
      el('h2', { id: 'titulo-analise', text: 'Análise da fotografia' }),
      d.visao
        ? renderizarAnaliseVisao(d.visao, { nivel: 3 })
        : el('p', { text: 'Esta denúncia não tem fotografia, por isso não passou pela triagem automática.' }),
    );

    const assistenteHref = `#/assistente?${new URLSearchParams({ protocolo: d.protocolo, modo: 'explicar_resultado', contexto: 'detalhe' }).toString()}`;
    const acoes = el(
      'div',
      { class: 'acoes' },
      el('a', { class: 'botao', href: assistenteHref, id: 'botao-perguntar-assistente' }, 'Perguntar ao assistente sobre esta denúncia'),
      el('a', { class: 'botao botao--secundario', href: '#/registrar' }, 'Registrar nova denúncia'),
    );

    area.replaceChildren(secaoStatus, acoes, secaoDados, secaoHistorico, secaoAnalise);
  }

  carregar();
}
