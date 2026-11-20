// Tela Assistente (#/assistente) — AcessaCidade Helper.
import { el, criarAviso } from '../ui.js';
import { PROTOCOLO_REGEX } from '../constants.js';
import { criarChat } from '../components/chat.js';

export const titulo = 'Assistente';

const CONTEXTOS_VALIDOS = /^[a-z_]{2,30}$/;

export function render({ container, consulta, signal }) {
  const protocolo = (consulta.get('protocolo') || '').trim().toUpperCase();
  const modo = consulta.get('modo') || (protocolo ? 'explicar_resultado' : 'geral');
  const contexto = consulta.get('contexto') || 'assistente';

  container.append(
    el(
      'div',
      { class: 'cabecalho-pagina' },
      el('h1', { tabindex: '-1', text: 'Assistente AcessaCidade' }),
      el(
        'p',
        {},
        'Tire dúvidas sobre como usar o AcessaCidade, peça ajuda para escrever a descrição do problema ou entenda o resultado da análise de uma foto.',
      ),
    ),
    criarAviso(
      'info',
      'Antes de começar',
      'O assistente pode usar inteligência artificial e pode errar. Ele não é um atendimento oficial do governo e não altera o status das denúncias.',
      'Não escreva dados pessoais, como CPF, telefone ou o endereço da sua casa.',
    ),
    criarChat({
      protocoloInicial: PROTOCOLO_REGEX.test(protocolo) ? protocolo : '',
      modoInicial: modo,
      contextoTela: CONTEXTOS_VALIDOS.test(contexto) ? contexto : 'assistente',
      signal,
    }),
  );
}
