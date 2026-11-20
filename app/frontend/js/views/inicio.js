// Tela Início (#/)
import { api, ApiError } from '../api.js';
import { el, criarAviso, criarCarregando, criarErroCarregamento, formatarDataHora } from '../ui.js';
import { criarIndicadores } from '../components/charts.js';
import { criarListaCartoes } from '../components/denuncia-card.js';

export const titulo = 'Início';

function blocoOds() {
  return el(
    'section',
    { class: 'secao', 'aria-labelledby': 'titulo-ods' },
    el('h2', { id: 'titulo-ods', text: 'Conexão com o ODS 11 — Cidades e comunidades sustentáveis' }),
    el(
      'div',
      { class: 'ods' },
      el('span', { class: 'ods__numero', 'aria-hidden': 'true', text: '11' }),
      el(
        'div',
        { class: 'ods__texto' },
        el(
          'p',
          {},
          'O AcessaCidade contribui com as metas ',
          el('strong', { text: '11.2' }),
          ' (acesso a sistemas de transporte seguros, acessíveis e sustentáveis, com atenção às pessoas com deficiência e idosas) e ',
          el('strong', { text: '11.7' }),
          ' (acesso universal a espaços públicos seguros, inclusivos e acessíveis).',
        ),
        el(
          'p',
          { class: 'texto-secundario' },
          'Calçadas sem buracos e sem obstáculos são o primeiro trecho de qualquer deslocamento: até o ponto de ônibus, a escola, o posto de saúde.',
        ),
      ),
    ),
  );
}

export function render({ container, signal }) {
  container.append(
    el(
      'section',
      { class: 'heroi', 'aria-labelledby': 'titulo-inicio' },
      el('h1', { id: 'titulo-inicio', tabindex: '-1', text: 'AcessaCidade' }),
      el(
        'p',
        { class: 'heroi__lead' },
        'Registre e acompanhe problemas de acessibilidade em calçadas e espaços públicos — buracos, calçadas quebradas, rampas irregulares e obstáculos — para que pessoas com deficiência, cadeirantes, idosos e pessoas com mobilidade reduzida possam circular com segurança.',
      ),
      el(
        'div',
        { class: 'acoes' },
        el('a', { class: 'botao botao--grande', href: '#/registrar' }, 'Registrar denúncia'),
        el('a', { class: 'botao botao--secundario botao--grande', href: '#/consultar' }, 'Consultar denúncias'),
      ),
    ),
    el(
      'section',
      { class: 'secao', 'aria-labelledby': 'titulo-problema' },
      el('h2', { id: 'titulo-problema', text: 'O problema' }),
      el(
        'p',
        {},
        'Um buraco ou um degrau na calçada pode ser só um incômodo para algumas pessoas, mas para quem usa cadeira de rodas, bengala, andador ou carrinho de bebê ele bloqueia o caminho ou causa quedas. Esses problemas costumam ficar sem registro organizado, sem foto e sem acompanhamento.',
      ),
      el('h3', { text: 'Como o AcessaCidade ajuda' }),
      el(
        'ol',
        { class: 'passos' },
        el('li', {}, el('strong', { text: 'Você registra' }), ' o problema com endereço, descrição e, se quiser, uma foto.'),
        el('li', {}, el('strong', { text: 'A foto passa por uma triagem automática' }), ' que destaca possíveis buracos e explica o resultado.'),
        el('li', {}, el('strong', { text: 'Uma pessoa da equipe revisa' }), ' e atualiza o status da denúncia.'),
        el('li', {}, el('strong', { text: 'Todos acompanham' }), ' pelo número de protocolo e pelo painel de indicadores.'),
      ),
    ),
  );

  const secaoIndicadores = el(
    'section',
    { class: 'secao', 'aria-labelledby': 'titulo-resumo', 'aria-busy': 'true' },
    el('h2', { id: 'titulo-resumo', text: 'Resumo das denúncias' }),
    criarCarregando('Carregando indicadores...'),
  );
  const secaoRecentes = el(
    'section',
    { 'aria-labelledby': 'titulo-recentes' },
    el('h2', { id: 'titulo-recentes', text: 'Ocorrências recentes' }),
    criarCarregando('Carregando ocorrências recentes...'),
  );
  container.append(
    secaoIndicadores,
    secaoRecentes,
    blocoOds(),
    criarAviso(
      'info',
      'Importante',
      'O AcessaCidade é um projeto acadêmico e não é um serviço oficial do governo. Registrar aqui não substitui os canais oficiais da prefeitura.',
      'Denúncias marcadas como "SIMULADO" são dados fictícios de demonstração, da cidade fictícia "Cidade Exemplo".',
    ),
  );

  async function carregar() {
    try {
      const ind = await api.indicadores(true, signal);
      if (signal.aborted) return;
      const porStatus = Array.isArray(ind.por_status) ? ind.por_status : [];
      const aguardando = porStatus.find((s) => s.chave === 'AGUARDANDO_REVISAO');
      secaoIndicadores.replaceChildren(
        el('h2', { id: 'titulo-resumo', text: 'Resumo das denúncias' }),
        criarIndicadores([
          { rotulo: 'Denúncias registradas', valor: ind.total },
          { rotulo: 'Possíveis buracos (triagem)', valor: ind.possiveis_buracos },
          { rotulo: 'Aguardando revisão', valor: aguardando ? aguardando.total : 0 },
          { rotulo: 'Sem fotografia', valor: ind.sem_imagem },
        ]),
        el(
          'p',
          { class: 'texto-secundario' },
          `Atualizado em ${formatarDataHora(ind.gerado_em)}. ${ind.inclui_simulados ? 'Inclui dados simulados de demonstração. ' : ''}`,
          el('a', { href: '#/painel', text: 'Ver o painel completo' }),
        ),
      );
      secaoIndicadores.removeAttribute('aria-busy');
      const recentes = Array.isArray(ind.recentes) ? ind.recentes.slice(0, 5) : [];
      secaoRecentes.replaceChildren(
        el('h2', { id: 'titulo-recentes', text: 'Ocorrências recentes' }),
        recentes.length
          ? criarListaCartoes(recentes, { nivel: 3 })
          : el('p', {}, 'Ainda não há denúncias registradas. ', el('a', { href: '#/registrar', text: 'Registre a primeira.' })),
        el('p', {}, el('a', { href: '#/consultar', text: 'Ver todas as denúncias' })),
      );
    } catch (erro) {
      if (erro instanceof ApiError && erro.tipo === 'cancelado') return;
      secaoIndicadores.removeAttribute('aria-busy');
      secaoIndicadores.replaceChildren(
        el('h2', { id: 'titulo-resumo', text: 'Resumo das denúncias' }),
        criarErroCarregamento(erro, carregar, 'Não foi possível carregar os indicadores'),
      );
      secaoRecentes.replaceChildren(
        el('h2', { id: 'titulo-recentes', text: 'Ocorrências recentes' }),
        el('p', { class: 'texto-secundario', text: 'As ocorrências recentes aparecem aqui quando o servidor responder.' }),
      );
    }
  }
  carregar();
}
