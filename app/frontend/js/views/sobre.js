// Tela Sobre, privacidade e LGPD (#/sobre)
import { el } from '../ui.js';

export const titulo = 'Sobre e privacidade';

function secao(id, tituloSecao, ...conteudo) {
  return el('section', { class: 'secao', 'aria-labelledby': id }, el('h2', { id, text: tituloSecao }), ...conteudo);
}

export function render({ container }) {
  container.append(
    el(
      'div',
      { class: 'cabecalho-pagina' },
      el('h1', { tabindex: '-1', text: 'Sobre o AcessaCidade' }),
      el('p', { class: 'subtitulo', text: 'O que é, como funciona, quais são os limites e como tratamos os seus dados.' }),
    ),
    secao(
      'sobre-o-que-e',
      'O que é',
      el(
        'p',
        {},
        'O AcessaCidade é uma plataforma cidadã para registrar e acompanhar problemas de acessibilidade em calçadas e espaços públicos: buracos, calçadas quebradas ou desniveladas, rampas ausentes, piso tátil danificado e obstáculos no caminho.',
      ),
      el(
        'p',
        {},
        'Foi pensado para pessoas com deficiência, cadeirantes, pessoas com mobilidade reduzida, idosos e para quem convive com elas. É um projeto acadêmico (FIAP Global Solution 2026.2 — CitizenTech).',
      ),
    ),
    secao(
      'sobre-como-funciona',
      'Como funciona',
      el(
        'ol',
        { class: 'passos' },
        el('li', {}, el('strong', { text: 'Registro: ' }), 'você informa o endereço, o tipo de problema, o impacto e uma descrição. A foto é opcional.'),
        el('li', {}, el('strong', { text: 'Tratamento da foto: ' }), 'a foto é conferida, os dados escondidos (EXIF, incluindo localização GPS) são removidos, o tamanho é reduzido e rostos detectados são borrados.'),
        el('li', {}, el('strong', { text: 'Triagem automática: ' }), 'um algoritmo de visão computacional procura sinais de buraco (regiões escuras, bordas, formato) e mostra cada etapa do processamento com explicações.'),
        el('li', {}, el('strong', { text: 'Protocolo: ' }), 'você recebe um número no formato AC-2026-000012 para acompanhar a denúncia.'),
        el('li', {}, el('strong', { text: 'Revisão humana: ' }), 'uma pessoa da equipe revisa o resultado, confirma ou descarta e atualiza o status.'),
        el('li', {}, el('strong', { text: 'Indicadores: ' }), 'os dados (sem nome) alimentam o painel e o pipeline de dados que gera indicadores por bairro, tipo e período.'),
      ),
      el('p', {}, 'Os status possíveis são: Recebida, Em análise, Aguardando revisão, Encaminhada e Resolvida.'),
    ),
    secao(
      'sobre-limites',
      'Limites da triagem automática',
      el(
        'ul',
        {},
        el('li', { text: 'A triagem é um apoio, não uma decisão. Ela pode errar e sempre pode ser revisada por uma pessoa.' }),
        el('li', { text: 'Sombras, manchas, folhas, água, piso escuro, pouca luz e fotos tremidas podem confundir o algoritmo.' }),
        el('li', { text: 'A pontuação mostrada é heurística: indica o quanto a foto combina com os sinais procurados. Não é uma probabilidade.' }),
        el('li', { text: 'O algoritmo foi pensado para buracos. Outros problemas (rampas, piso tátil, obstáculos) dependem da descrição e da revisão humana.' }),
      ),
    ),
    secao(
      'sobre-privacidade',
      'Privacidade e LGPD',
      el('h3', { text: 'O que coletamos' }),
      el(
        'ul',
        {},
        el('li', { text: 'Endereço do problema, tipo, impacto, descrição e, se você quiser, latitude e longitude.' }),
        el('li', { text: 'A foto do local, depois do tratamento de privacidade (sem EXIF/GPS, reduzida e com rostos borrados).' }),
        el('li', { text: 'Nome ou apelido, somente se você preencher. Ele é opcional, nunca aparece na plataforma e não é enviado para exportações ou indicadores.' }),
      ),
      el('h3', { text: 'Por que coletamos' }),
      el(
        'p',
        { text: 'Somente para registrar, analisar, acompanhar e gerar indicadores sobre problemas de acessibilidade. Não vendemos dados e não usamos os dados para outras finalidades.' },
      ),
      el('h3', { text: 'Por quanto tempo' }),
      el('p', { text: 'Política de retenção: [PREENCHER: prazo de guarda das denúncias e das fotos e como ocorre a exclusão].' }),
      el('h3', { text: 'Assistente com IA' }),
      el(
        'p',
        { text: 'As perguntas feitas ao assistente podem ser enviadas a um serviço de inteligência artificial para gerar a resposta. Não escreva dados pessoais nas perguntas. Sem esse serviço, o assistente funciona em um modo básico com respostas prontas.' },
      ),
      el('h3', { text: 'Seus direitos' }),
      el(
        'p',
        { text: 'Pela LGPD, você pode pedir informações, correção ou exclusão de dados pessoais. Use o contato abaixo e informe o número do protocolo.' },
      ),
    ),
    secao(
      'sobre-ods',
      'Objetivos de Desenvolvimento Sustentável (ODS)',
      el(
        'div',
        { class: 'ods' },
        el('span', { class: 'ods__numero', 'aria-hidden': 'true', text: '11' }),
        el(
          'div',
          { class: 'ods__texto' },
          el('h3', { text: 'ODS 11 — Cidades e comunidades sustentáveis' }),
          el(
            'p',
            { text: 'Meta 11.2: acesso a sistemas de transporte seguros e acessíveis, com atenção a pessoas com deficiência e idosas. Meta 11.7: acesso universal a espaços públicos seguros, inclusivos e acessíveis.' },
          ),
        ),
      ),
      el('hr', { class: 'separador' }),
      el(
        'div',
        { class: 'ods' },
        el('span', { class: 'ods__numero ods__numero--10', 'aria-hidden': 'true', text: '10' }),
        el(
          'div',
          { class: 'ods__texto' },
          el('h3', { text: 'ODS 10 — Redução das desigualdades' }),
          el('p', { text: 'Meta 10.2: promover a inclusão social, econômica e política de todas as pessoas, incluindo pessoas com deficiência.' }),
        ),
      ),
    ),
    secao(
      'sobre-oficial',
      'Não é um serviço oficial',
      el(
        'p',
        { text: 'O AcessaCidade não é um serviço oficial do governo. Registrar uma denúncia aqui não substitui os canais oficiais da prefeitura. O status "Resolvida" é um registro da equipe do projeto e não representa confirmação de órgão público.' },
      ),
      el(
        'p',
        { text: 'Denúncias marcadas como "SIMULADO" são dados fictícios, da cidade fictícia "Cidade Exemplo", usados apenas para demonstração.' },
      ),
    ),
    secao('sobre-contato', 'Contato', el('p', { text: 'Contato da equipe: [PREENCHER: e-mail ou canal de contato da equipe].' })),
  );
}
