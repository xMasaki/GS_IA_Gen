// Chat acessível com o AcessaCidade Helper (POST /api/assistente — contrato 4.9).
import { api, ApiError } from '../api.js';
import { el, anunciar, focar, hrefDenuncia, idUnico } from '../ui.js';
import { LIMITES, MODOS_ASSISTENTE, PROTOCOLO_REGEX } from '../constants.js';

// A conversa fica apenas na memória desta aba (some ao recarregar a página).
const conversa = [];

const SUGESTOES = {
  geral: [
    'Como registro uma denúncia?',
    'O que significa "Aguardando revisão"?',
    'O AcessaCidade é um serviço da prefeitura?',
    'Quais dados pessoais vocês guardam?',
  ],
  descricao: [
    'Me ajude a descrever um buraco grande na calçada em frente a um ponto de ônibus.',
    'Que informações devo colocar na descrição do problema?',
    'Como descrevo uma rampa irregular para cadeira de rodas?',
  ],
  explicar_resultado: [
    'Explique o resultado da análise da foto desta denúncia.',
    'O que significa a pontuação heurística?',
    'Por que a análise pode dar inconclusiva?',
  ],
};

/** Converte texto simples (com marcações leves de lista e **negrito**) em elementos seguros. */
function textoParaElementos(texto) {
  const fragmentos = [];
  const linhas = String(texto || '').replace(/\r\n/g, '\n').split('\n');
  let lista = null;
  let tipoLista = null;
  const inline = (linha) => {
    const partes = linha.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
    return partes.map((p) => (/^\*\*[^*]+\*\*$/.test(p) ? el('strong', { text: p.slice(2, -2) }) : p));
  };
  for (const bruta of linhas) {
    const linha = bruta.trim();
    const marcador = /^[-*•]\s+(.*)$/.exec(linha);
    const numerado = /^\d+[.)]\s+(.*)$/.exec(linha);
    if (marcador || numerado) {
      const tipo = marcador ? 'ul' : 'ol';
      if (!lista || tipoLista !== tipo) {
        lista = el(tipo, {});
        tipoLista = tipo;
        fragmentos.push(lista);
      }
      lista.appendChild(el('li', {}, inline((marcador || numerado)[1])));
      continue;
    }
    lista = null;
    tipoLista = null;
    if (!linha) continue;
    const titulo = /^#{1,6}\s+(.*)$/.exec(linha);
    fragmentos.push(el('p', {}, titulo ? el('strong', { text: titulo[1] }) : inline(linha)));
  }
  return fragmentos.length ? fragmentos : [el('p', { text: String(texto || '') })];
}

function criarMensagemElemento(m) {
  if (m.papel === 'usuario') {
    return el('div', { class: 'msg msg--usuario' }, el('span', { class: 'msg__autor', text: 'Você' }), textoParaElementos(m.texto));
  }
  if (m.papel === 'erro') {
    return el('div', { class: 'msg msg--erro' }, el('span', { class: 'msg__autor', text: 'Aviso do sistema' }), el('p', { text: m.texto }));
  }
  const fonte =
    m.fonte === 'llm'
      ? `Fonte: IA generativa${m.modelo ? ` (modelo ${m.modelo})` : ''}. A IA pode errar; confira as informações importantes.`
      : 'Fonte: modo básico (respostas prontas baseadas em regras, sem IA generativa).';
  return el(
    'div',
    { class: 'msg msg--assistente' },
    el('span', { class: 'msg__autor', text: 'Assistente AcessaCidade' }),
    textoParaElementos(m.texto),
    m.denuncia_referenciada
      ? el('p', { class: 'msg__fonte' }, 'Denúncia consultada: ', el('a', { href: hrefDenuncia(m.denuncia_referenciada), text: m.denuncia_referenciada }))
      : null,
    el('p', { class: 'msg__fonte', text: fonte }),
    Array.isArray(m.avisos) && m.avisos.length ? el('ul', { class: 'msg__avisos', 'aria-label': 'Avisos' }, m.avisos.map((a) => el('li', { text: String(a) }))) : null,
  );
}

/** Últimas 6 mensagens válidas, no formato do contrato. */
function montarHistorico() {
  return conversa
    .filter((m) => (m.papel === 'usuario' || m.papel === 'assistente') && m.noHistorico !== false)
    .slice(-6)
    .map((m) => ({ papel: m.papel, texto: String(m.texto).slice(0, LIMITES.mensagemAssistente.max) }));
}

/**
 * @param {{protocoloInicial?: string, modoInicial?: string, contextoTela?: string, signal?: AbortSignal}} cfg
 */
export function criarChat({ protocoloInicial = '', modoInicial = 'geral', contextoTela = 'assistente', signal } = {}) {
  const modoValido = MODOS_ASSISTENTE.some((m) => m.chave === modoInicial) ? modoInicial : 'geral';

  const log = el('div', {
    class: 'chat__log',
    id: 'assistente-log',
    role: 'log',
    'aria-live': 'polite',
    'aria-relevant': 'additions',
    'aria-label': 'Conversa com o assistente',
    tabindex: '0',
  });
  const vazio = el('p', { class: 'chat__vazio', text: 'Ainda não há mensagens. Escreva sua pergunta ou escolha uma sugestão abaixo.' });

  const seletorModo = el(
    'select',
    { id: 'assistente-modo', name: 'modo', 'aria-describedby': 'assistente-modo-dica' },
    MODOS_ASSISTENTE.map((m) => el('option', { value: m.chave, text: m.rotulo, selected: m.chave === modoValido })),
  );
  seletorModo.value = modoValido;
  const campoProtocolo = el('input', {
    type: 'text',
    id: 'assistente-protocolo',
    name: 'protocolo',
    autocomplete: 'off',
    spellcheck: 'false',
    inputmode: 'text',
    maxlength: '20',
    placeholder: 'AC-2026-000012',
    'aria-describedby': 'assistente-protocolo-dica',
    value: protocoloInicial || '',
  });
  const erroProtocolo = el('p', { class: 'campo-erro', id: 'assistente-protocolo-erro', hidden: true });
  const campoMensagem = el('textarea', {
    id: 'assistente-mensagem',
    name: 'mensagem',
    rows: '3',
    maxlength: String(LIMITES.mensagemAssistente.max),
    'aria-describedby': 'assistente-mensagem-dica assistente-mensagem-contador',
  });
  const contador = el('span', { class: 'contador', id: 'assistente-mensagem-contador', text: `0 de ${LIMITES.mensagemAssistente.max} caracteres` });
  const erroMensagem = el('p', { class: 'campo-erro', id: 'assistente-mensagem-erro', hidden: true });
  const botaoEnviar = el('button', { type: 'submit', class: 'botao', id: 'assistente-enviar' }, 'Enviar pergunta');
  const estado = el('p', { class: 'status-inline', role: 'status', id: 'assistente-estado' });

  const listaSugestoes = el('ul', { class: 'sugestoes', 'aria-label': 'Sugestões de perguntas' });

  function renderizarLog() {
    log.replaceChildren(...(conversa.length ? conversa.map(criarMensagemElemento) : [vazio]));
    log.scrollTop = log.scrollHeight;
  }

  function adicionar(m) {
    conversa.push(m);
    if (conversa.length > 40) conversa.splice(0, conversa.length - 40);
    if (vazio.isConnected) vazio.remove();
    log.appendChild(criarMensagemElemento(m));
    log.scrollTop = log.scrollHeight;
  }

  function mostrarErroCampo(campo, caixa, mensagem) {
    const ids = (campo.getAttribute('aria-describedby') || '').split(' ').filter((i) => i && i !== caixa.id);
    if (mensagem) {
      caixa.textContent = mensagem;
      caixa.hidden = false;
      campo.setAttribute('aria-invalid', 'true');
      ids.push(caixa.id);
    } else {
      caixa.hidden = true;
      campo.removeAttribute('aria-invalid');
    }
    campo.setAttribute('aria-describedby', ids.join(' '));
  }

  function renderizarSugestoes() {
    const modo = seletorModo.value;
    listaSugestoes.replaceChildren(
      ...(SUGESTOES[modo] || SUGESTOES.geral).map((texto) =>
        el(
          'li',
          {},
          el(
            'button',
            {
              type: 'button',
              class: 'botao botao--secundario botao--compacto',
              on: {
                click: () => {
                  campoMensagem.value = texto;
                  atualizarContador();
                  enviar();
                },
              },
            },
            texto,
          ),
        ),
      ),
    );
  }

  function atualizarContador() {
    contador.textContent = `${campoMensagem.value.length} de ${LIMITES.mensagemAssistente.max} caracteres`;
  }

  let enviando = false;
  async function enviar() {
    if (enviando) return;
    const mensagem = campoMensagem.value.trim();
    const protocolo = campoProtocolo.value.trim().toUpperCase();
    let valido = true;
    if (!mensagem) {
      mostrarErroCampo(campoMensagem, erroMensagem, 'Escreva sua pergunta antes de enviar.');
      valido = false;
    } else if (mensagem.length > LIMITES.mensagemAssistente.max) {
      mostrarErroCampo(campoMensagem, erroMensagem, `A pergunta pode ter no máximo ${LIMITES.mensagemAssistente.max} caracteres.`);
      valido = false;
    } else {
      mostrarErroCampo(campoMensagem, erroMensagem, '');
    }
    if (protocolo && !PROTOCOLO_REGEX.test(protocolo)) {
      mostrarErroCampo(campoProtocolo, erroProtocolo, 'Protocolo em formato inválido. Use o formato AC-2026-000012, ou deixe o campo em branco.');
      if (valido) focar(campoProtocolo, { rolar: false });
      valido = false;
    } else {
      mostrarErroCampo(campoProtocolo, erroProtocolo, '');
    }
    if (!valido) {
      if (!mensagem || mensagem.length > LIMITES.mensagemAssistente.max) focar(campoMensagem, { rolar: false });
      return;
    }

    const historico = montarHistorico();
    const msgUsuario = { papel: 'usuario', texto: mensagem };
    adicionar(msgUsuario);
    campoMensagem.value = '';
    atualizarContador();

    enviando = true;
    botaoEnviar.disabled = true;
    botaoEnviar.textContent = 'Aguardando resposta...';
    estado.textContent = 'O assistente está preparando a resposta...';
    log.setAttribute('aria-busy', 'true');
    const payload = {
      mensagem,
      modo: seletorModo.value,
      contexto_tela: contextoTela,
      historico,
    };
    if (protocolo) payload.protocolo = protocolo;
    try {
      const r = await api.perguntarAssistente(payload, signal);
      adicionar({
        papel: 'assistente',
        texto: r && r.resposta ? r.resposta : 'O assistente não enviou uma resposta.',
        fonte: r && r.fonte,
        modelo: r && r.modelo,
        avisos: (r && r.avisos) || [],
        denuncia_referenciada: r && r.denuncia_referenciada && PROTOCOLO_REGEX.test(r.denuncia_referenciada) ? r.denuncia_referenciada : null,
      });
      estado.textContent = 'Resposta recebida.';
    } catch (erro) {
      if (erro instanceof ApiError && erro.tipo === 'cancelado') return;
      msgUsuario.noHistorico = false;
      campoMensagem.value = mensagem; // devolve o texto para tentar de novo
      atualizarContador();
      adicionar({ papel: 'erro', texto: `Não foi possível obter a resposta. ${erro.message}` });
      estado.textContent = 'Ocorreu um erro. Sua pergunta continua no campo para você tentar de novo.';
    } finally {
      enviando = false;
      botaoEnviar.disabled = false;
      botaoEnviar.textContent = 'Enviar pergunta';
      log.removeAttribute('aria-busy');
    }
  }

  campoMensagem.addEventListener('input', atualizarContador);
  campoMensagem.addEventListener('keydown', (ev) => {
    // Ctrl+Enter envia (Enter sozinho cria nova linha)
    if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) {
      ev.preventDefault();
      enviar();
    }
  });
  seletorModo.addEventListener('change', renderizarSugestoes);

  const form = el(
    'form',
    {
      class: 'secao',
      id: 'form-assistente',
      novalidate: true,
      'aria-labelledby': 'titulo-form-assistente',
      on: {
        submit: (ev) => {
          ev.preventDefault();
          enviar();
        },
      },
    },
    el('h2', { id: 'titulo-form-assistente', text: 'Faça sua pergunta' }),
    el(
      'div',
      { class: 'linha-campos' },
      el(
        'div',
        { class: 'campo' },
        el('label', { for: 'assistente-modo', text: 'Tipo de ajuda' }),
        el('span', { class: 'dica', id: 'assistente-modo-dica', text: 'Escolha o que você precisa. As sugestões mudam conforme a escolha.' }),
        seletorModo,
      ),
      el(
        'div',
        { class: 'campo' },
        el('label', { for: 'assistente-protocolo' }, 'Protocolo da denúncia ', el('span', { class: 'opcional', text: '(opcional)' })),
        el('span', { class: 'dica', id: 'assistente-protocolo-dica', text: 'Informe para perguntar sobre uma denúncia específica. Formato: AC-2026-000012.' }),
        campoProtocolo,
        erroProtocolo,
      ),
    ),
    el(
      'div',
      { class: 'campo' },
      el('label', { for: 'assistente-mensagem' }, 'Sua pergunta ', el('span', { class: 'obrigatorio', text: '(obrigatório)' })),
      el('span', { class: 'dica', id: 'assistente-mensagem-dica', text: 'Não escreva dados pessoais (como CPF, telefone ou endereço da sua casa). Para enviar pelo teclado: Ctrl + Enter.' }),
      campoMensagem,
      contador,
      erroMensagem,
    ),
    el(
      'div',
      { class: 'acoes' },
      botaoEnviar,
      el(
        'button',
        {
          type: 'button',
          class: 'botao botao--secundario',
          id: 'assistente-limpar',
          on: {
            click: () => {
              conversa.length = 0;
              renderizarLog();
              anunciar('Conversa apagada.');
              focar(campoMensagem, { rolar: false });
            },
          },
        },
        'Limpar conversa',
      ),
    ),
    estado,
  );

  renderizarSugestoes();
  renderizarLog();

  const idTituloLog = idUnico('titulo-log');
  return el(
    'div',
    { class: 'chat' },
    el('section', { 'aria-labelledby': idTituloLog }, el('h2', { id: idTituloLog, text: 'Conversa' }), log),
    form,
    el('section', { class: 'secao', 'aria-labelledby': 'titulo-sugestoes' }, el('h2', { id: 'titulo-sugestoes', text: 'Sugestões de perguntas' }), listaSugestoes),
  );
}
