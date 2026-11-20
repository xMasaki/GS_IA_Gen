// Página 404 amigável (rota inexistente).
import { el } from '../ui.js';

export const titulo = 'Página não encontrada';

export function render({ container }) {
  container.append(
    el(
      'section',
      { class: 'secao', 'aria-labelledby': 'titulo-404' },
      el('h1', { id: 'titulo-404', tabindex: '-1', text: 'Página não encontrada' }),
      el('p', {}, 'O endereço que você abriu não existe no AcessaCidade. Ele pode ter sido digitado errado ou a página mudou de lugar.'),
      el('p', {}, 'Você pode:'),
      el(
        'ul',
        {},
        el('li', {}, el('a', { href: '#/', text: 'Voltar para o início' })),
        el('li', {}, el('a', { href: '#/registrar', text: 'Registrar uma denúncia' })),
        el('li', {}, el('a', { href: '#/consultar', text: 'Consultar uma denúncia pelo protocolo' })),
        el('li', {}, el('a', { href: '#/assistente?contexto=nao_encontrada', text: 'Pedir ajuda ao assistente' })),
      ),
    ),
  );
}
