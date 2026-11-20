// Carrega as enumerações de GET /api/meta/opcoes com fallback embutido (contrato seção 3).
// O formato exato da resposta não é fixado pelo contrato; este módulo aceita listas
// [{chave, rotulo}] ou mapas {CHAVE: "Rótulo"} / {CHAVE: {rotulo, significado}}.

import { api } from './api.js';
import { OPCOES_PADRAO, MAX_UPLOAD_MB_PADRAO } from './constants.js';

const ALIASES = {
  tipo_obstaculo: ['tipo_obstaculo', 'tipos_obstaculo', 'tipos'],
  impacto: ['impacto', 'impactos'],
  status: ['status', 'statuses'],
  classificacao_visao: ['classificacao_visao', 'visao_classificacao', 'classificacao', 'classificacoes', 'visao'],
  origem: ['origem', 'origens'],
  revisao_humana: ['revisao_humana', 'revisoes_humanas'],
};

function normalizarItem(item, chaveMapa) {
  if (typeof item === 'string') {
    return chaveMapa ? { chave: chaveMapa, rotulo: item } : { chave: item, rotulo: item };
  }
  if (!item || typeof item !== 'object') return null;
  const chave = chaveMapa ?? item.chave ?? item.valor ?? item.value ?? item.key ?? item.codigo;
  if (chave === null || chave === undefined || chave === '') return null;
  return {
    chave: String(chave),
    rotulo: String(item.rotulo ?? item.label ?? item.nome ?? chave),
    significado: item.significado ?? item.descricao ?? undefined,
  };
}

function normalizarLista(valor) {
  if (Array.isArray(valor)) return valor.map((i) => normalizarItem(i)).filter(Boolean);
  if (valor && typeof valor === 'object') {
    return Object.entries(valor)
      .map(([k, v]) => normalizarItem(v, k))
      .filter(Boolean);
  }
  return [];
}

/** Converte a resposta da API no formato interno, completando com o fallback. */
export function normalizarOpcoes(resposta) {
  const raiz = resposta && typeof resposta === 'object' && resposta.opcoes && typeof resposta.opcoes === 'object' ? resposta.opcoes : resposta || {};
  const resultado = { origemDados: 'api' };
  for (const [grupo, nomes] of Object.entries(ALIASES)) {
    let lista = [];
    for (const nome of nomes) {
      if (raiz[nome] !== undefined) {
        lista = normalizarLista(raiz[nome]);
        if (lista.length) break;
      }
    }
    const padrao = OPCOES_PADRAO[grupo];
    if (!lista.length) {
      lista = padrao.map((i) => ({ ...i }));
    } else {
      // completa "significado" a partir do contrato quando a API não envia
      lista = lista.map((i) => {
        const ref = padrao.find((p) => p.chave === i.chave);
        return { ...i, significado: i.significado || (ref && ref.significado) || undefined };
      });
    }
    resultado[grupo] = lista;
  }
  const max = Number(raiz.max_upload_mb ?? raiz.maxUploadMb);
  resultado.max_upload_mb = Number.isFinite(max) && max > 0 ? max : MAX_UPLOAD_MB_PADRAO;
  return resultado;
}

export function opcoesPadrao() {
  const r = normalizarOpcoes({});
  r.origemDados = 'fallback';
  return r;
}

let cache = null;
let promessa = null;

/** Retorna as opções (com cache). Nunca rejeita: em caso de falha usa o fallback. */
export function carregarOpcoes() {
  if (cache) return Promise.resolve(cache);
  if (!promessa) {
    promessa = api
      .opcoes()
      .then((resp) => {
        cache = normalizarOpcoes(resp);
        return cache;
      })
      .catch(() => opcoesPadrao())
      .finally(() => {
        promessa = null;
      });
  }
  return promessa;
}

/** Opções já carregadas ou o fallback (síncrono). */
export function opcoesAtuais() {
  return cache || opcoesPadrao();
}

export function rotuloDe(grupo, chave, opcoes = opcoesAtuais()) {
  if (!chave) return '';
  const item = (opcoes[grupo] || []).find((i) => i.chave === chave);
  return item ? item.rotulo : chave;
}

export function significadoStatus(chave, opcoes = opcoesAtuais()) {
  const item = (opcoes.status || []).find((i) => i.chave === chave);
  return item && item.significado ? item.significado : '';
}
