// Cartão resumido de uma denúncia (listagens: início, consulta, revisão).
import {
  el,
  criarSeloSimulado,
  criarSeloStatus,
  criarSeloVisao,
  formatarDataHora,
  formatarEndereco,
  hrefDenuncia,
  truncar,
} from '../ui.js';
import { ROTULO_SEM_FOTO } from '../constants.js';
import { rotuloDe } from '../opcoes.js';

export function rotuloVisao(d) {
  if (!d.visao) return { chave: null, rotulo: ROTULO_SEM_FOTO };
  return { chave: d.visao.classificacao, rotulo: d.visao.rotulo || rotuloDe('classificacao_visao', d.visao.classificacao) };
}

/**
 * @param {object} d objeto Denuncia (contrato 4.1)
 * @param {{nivel?: number, acoes?: HTMLElement[]}} opcoes
 */
export function criarCartaoDenuncia(d, { nivel = 3, acoes = [] } = {}) {
  const visao = rotuloVisao(d);
  const titulo = el(
    `h${nivel}`,
    { class: 'cartao__titulo' },
    el('a', { href: hrefDenuncia(d.protocolo) }, el('span', { class: 'sr-only', text: 'Denúncia ' }), d.protocolo),
  );
  const selos = el(
    'div',
    { class: 'selos' },
    criarSeloStatus(d.status, d.status_rotulo || rotuloDe('status', d.status)),
    d.simulado ? criarSeloSimulado() : null,
  );
  const dl = el(
    'dl',
    { class: 'cartao__dl' },
    el('dt', { text: 'Data' }),
    el('dd', { text: formatarDataHora(d.criado_em) }),
    el('dt', { text: 'Local' }),
    el('dd', { text: formatarEndereco(d) }),
    el('dt', { text: 'Tipo' }),
    el('dd', { text: d.tipo_obstaculo_rotulo || rotuloDe('tipo_obstaculo', d.tipo_obstaculo) }),
    el('dt', { text: 'Impacto' }),
    el('dd', { text: d.impacto_rotulo || rotuloDe('impacto', d.impacto) || 'Não informado' }),
  );
  return el(
    'article',
    { class: 'cartao' },
    titulo,
    selos,
    dl,
    d.descricao ? el('p', { class: 'cartao__descricao', text: truncar(d.descricao, 140) }) : null,
    el('div', { class: 'cartao__rodape' }, criarSeloVisao(visao.chave, visao.rotulo), ...acoes),
  );
}

export function criarListaCartoes(denuncias, opcoes) {
  return el(
    'ul',
    { class: 'lista-cartoes' },
    denuncias.map((d) => el('li', {}, criarCartaoDenuncia(d, opcoes))),
  );
}
