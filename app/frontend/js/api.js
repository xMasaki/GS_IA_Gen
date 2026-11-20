// Cliente da API REST do AcessaCidade (mesma origem). Contrato: seção 4.
// - timeout via AbortController
// - erros convertidos em mensagens compreensíveis em português (ApiError)

const TIMEOUT_PADRAO_MS = 15000;

/** Nomes amigáveis dos campos para mensagens de erro de validação. */
export const NOMES_CAMPOS = {
  nome: 'Nome',
  logradouro: 'Logradouro (rua)',
  numero: 'Número',
  bairro: 'Bairro',
  cidade: 'Cidade',
  ponto_referencia: 'Ponto de referência',
  tipo_obstaculo: 'Tipo de obstáculo',
  descricao: 'Descrição',
  impacto: 'Impacto',
  latitude: 'Latitude',
  longitude: 'Longitude',
  consentimento: 'Consentimento',
  origem: 'Origem',
  foto: 'Fotografia',
  status: 'Status',
  observacao: 'Observação',
  revisao_humana: 'Revisão humana',
  mensagem: 'Mensagem',
  modo: 'Modo',
  protocolo: 'Protocolo',
  historico: 'Histórico da conversa',
};

export class ApiError extends Error {
  /**
   * @param {string} mensagem mensagem pronta para exibir
   * @param {{status?: number, tipo?: string, detalhes?: Array<{campo: string|null, mensagem: string}>, tentarApos?: number|null}} info
   */
  constructor(mensagem, { status = 0, tipo = 'http', detalhes = [], tentarApos = null } = {}) {
    super(mensagem);
    this.name = 'ApiError';
    this.status = status;
    this.tipo = tipo; // http | rede | timeout | cancelado
    this.detalhes = detalhes;
    this.tentarApos = tentarApos;
  }
}

/** Traduz mensagens técnicas comuns do Pydantic/FastAPI (em inglês) para português. */
function traduzirMensagem(msg) {
  const texto = String(msg || '').replace(/^Value error,\s*/i, '').trim();
  const regras = [
    [/^Field required$/i, 'campo obrigatório'],
    [/^String should have at least (\d+) characters?$/i, 'deve ter pelo menos $1 caracteres'],
    [/^String should have at most (\d+) characters?$/i, 'deve ter no máximo $1 caracteres'],
    [/^Input should be a valid number.*$/i, 'deve ser um número válido'],
    [/^Input should be a valid boolean.*$/i, 'valor inválido (esperado verdadeiro ou falso)'],
    [/^Input should be (less|greater) than or equal to (-?[\d.]+)$/i, (m, tipo, n) => `deve ser ${tipo === 'less' ? 'menor' : 'maior'} ou igual a ${n}`],
    [/^Input should be (.+)$/i, 'valor não permitido (esperado: $1)'],
  ];
  for (const [re, sub] of regras) {
    if (re.test(texto)) return texto.replace(re, sub);
  }
  return texto;
}

/**
 * Normaliza o campo `detail` do FastAPI (string, lista de erros do Pydantic ou objeto)
 * em uma lista [{campo, mensagem}].
 */
export function extrairDetalhes(detail) {
  if (detail === null || detail === undefined) return [];
  if (typeof detail === 'string') return [{ campo: null, mensagem: detail }];
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (typeof item === 'string') return { campo: null, mensagem: item };
      const loc = Array.isArray(item?.loc) ? item.loc : [];
      const campo = [...loc].reverse().find((p) => typeof p === 'string' && !['body', 'query', 'path', 'header', 'form'].includes(p)) || null;
      return { campo, mensagem: traduzirMensagem(item?.msg ?? item?.mensagem ?? JSON.stringify(item)) };
    });
  }
  if (typeof detail === 'object') {
    const msg = detail.mensagem || detail.message || detail.msg;
    if (msg) return [{ campo: detail.campo || null, mensagem: String(msg) }];
    return [{ campo: null, mensagem: JSON.stringify(detail) }];
  }
  return [{ campo: null, mensagem: String(detail) }];
}

/** Formata a lista de detalhes como texto corrido. */
export function detalhesComoTexto(detalhes) {
  return detalhes
    .map((d) => (d.campo ? `${NOMES_CAMPOS[d.campo] || d.campo}: ${d.mensagem}` : d.mensagem))
    .join(' ');
}

function mensagemPorStatus(status, detalhes, tentarApos) {
  const textoDetalhe = detalhesComoTexto(detalhes);
  switch (status) {
    case 400:
      return textoDetalhe || 'A requisição não pôde ser processada. Confira os dados e tente novamente.';
    case 401:
      return textoDetalhe || 'Acesso não autorizado. Confira o token e tente novamente.';
    case 403:
      return textoDetalhe || 'Esta funcionalidade está desativada neste ambiente.';
    case 404:
      return textoDetalhe || 'Não encontramos o que você procurou.';
    case 413:
      return 'O arquivo enviado é grande demais. Escolha uma foto menor ou reduza o tamanho da imagem.';
    case 415:
      return textoDetalhe || 'Formato de arquivo não aceito. Use JPEG, PNG ou WEBP.';
    case 422:
      return textoDetalhe
        ? `Alguns dados precisam ser corrigidos. ${textoDetalhe}`
        : 'Alguns dados precisam ser corrigidos. Confira os campos e tente novamente.';
    case 429: {
      const espera = tentarApos ? ` Aguarde cerca de ${tentarApos} segundo(s)` : ' Aguarde um minuto';
      return `Muitas tentativas em pouco tempo.${espera} e tente novamente.`;
    }
    case 503:
      return 'O serviço está temporariamente indisponível. Tente novamente em alguns minutos.';
    default:
      if (status >= 500) {
        return 'Ocorreu um erro no servidor. Seus dados não foram perdidos por nossa parte: tente novamente em alguns instantes.';
      }
      return textoDetalhe || `Erro inesperado (código ${status}).`;
  }
}

/**
 * Faz uma requisição à API.
 * @param {string} caminho ex.: "/api/denuncias"
 * @param {{metodo?: string, corpo?: any, cabecalhos?: Record<string,string>, timeoutMs?: number, signal?: AbortSignal, consulta?: Record<string, any>}} opcoes
 */
export async function requisitar(caminho, opcoes = {}) {
  const { metodo = 'GET', corpo, cabecalhos = {}, timeoutMs = TIMEOUT_PADRAO_MS, signal, consulta } = opcoes;

  let url = caminho;
  if (consulta) {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(consulta)) {
      if (v === null || v === undefined || v === '') continue;
      params.set(k, String(v));
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  const controlador = new AbortController();
  let estourouTempo = false;
  const temporizador = window.setTimeout(() => {
    estourouTempo = true;
    controlador.abort();
  }, timeoutMs);
  const repassarCancelamento = () => controlador.abort();
  if (signal) {
    if (signal.aborted) controlador.abort();
    else signal.addEventListener('abort', repassarCancelamento, { once: true });
  }

  const headers = { Accept: 'application/json', ...cabecalhos };
  let body;
  if (corpo instanceof FormData) {
    body = corpo; // o navegador define o boundary do multipart
  } else if (corpo !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(corpo);
  }

  let resposta;
  try {
    resposta = await fetch(url, {
      method: metodo,
      headers,
      body,
      signal: controlador.signal,
      credentials: 'same-origin',
      cache: 'no-store',
    });
  } catch (erro) {
    window.clearTimeout(temporizador);
    if (signal) signal.removeEventListener('abort', repassarCancelamento);
    if (estourouTempo) {
      throw new ApiError('O servidor demorou demais para responder. Verifique sua conexão e tente novamente.', { tipo: 'timeout' });
    }
    if (signal && signal.aborted) {
      throw new ApiError('Requisição cancelada.', { tipo: 'cancelado' });
    }
    throw new ApiError('Não foi possível conectar ao servidor. Verifique sua conexão com a internet e tente novamente.', {
      tipo: 'rede',
    });
  }

  let dados = null;
  try {
    const tipoConteudo = resposta.headers.get('content-type') || '';
    if (tipoConteudo.includes('application/json')) {
      dados = await resposta.json();
    } else {
      const texto = await resposta.text();
      dados = texto ? { detail: texto.slice(0, 300) } : null;
    }
  } catch {
    dados = null;
  } finally {
    window.clearTimeout(temporizador);
    if (signal) signal.removeEventListener('abort', repassarCancelamento);
  }

  if (!resposta.ok) {
    const detalhes = resposta.status >= 500 ? [] : extrairDetalhes(dados && dados.detail);
    const retry = Number.parseInt(resposta.headers.get('retry-after') || '', 10);
    const tentarApos = Number.isFinite(retry) ? retry : null;
    throw new ApiError(mensagemPorStatus(resposta.status, detalhes, tentarApos), {
      status: resposta.status,
      detalhes,
      tentarApos,
    });
  }
  return dados;
}

// ---------------- rotas da API (contrato seção 4) ----------------

export const api = {
  opcoes: (signal) => requisitar('/api/meta/opcoes', { signal, timeoutMs: 8000 }),

  listarDenuncias: (filtros, signal) => requisitar('/api/denuncias', { consulta: filtros, signal }),

  obterDenuncia: (ref, signal) => requisitar(`/api/denuncias/${encodeURIComponent(ref)}`, { signal }),

  criarDenuncia: (formData, signal) =>
    requisitar('/api/denuncias', { metodo: 'POST', corpo: formData, signal, timeoutMs: 90000 }),

  analisarFoto: (formData, signal) =>
    requisitar('/api/visao/analisar', { metodo: 'POST', corpo: formData, signal, timeoutMs: 90000 }),

  atualizarStatus: (id, corpo, token, signal) =>
    requisitar(`/api/denuncias/${encodeURIComponent(id)}/status`, {
      metodo: 'PATCH',
      corpo,
      cabecalhos: { 'X-Admin-Token': token },
      signal,
    }),

  indicadores: (incluirSimulados, signal) =>
    requisitar('/api/indicadores', { consulta: { incluir_simulados: incluirSimulados ? 'true' : 'false' }, signal }),

  indicadoresAnaliticos: (signal) => requisitar('/api/indicadores/analiticos', { signal }),

  perguntarAssistente: (payload, signal) =>
    requisitar('/api/assistente', { metodo: 'POST', corpo: payload, signal, timeoutMs: 60000 }),
};
