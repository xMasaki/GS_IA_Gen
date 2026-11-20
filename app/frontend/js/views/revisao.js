// Tela Área da equipe (#/revisao) — PATCH /api/denuncias/{id}/status com X-Admin-Token.
import { api, ApiError, NOMES_CAMPOS } from '../api.js';
import {
  el,
  anunciar,
  focar,
  criarAviso,
  criarCarregando,
  criarErroCarregamento,
  criarSeloStatus,
  criarSeloVisao,
  formatarNumero,
  urlImagemSegura,
  hrefDenuncia,
} from '../ui.js';
import { REVISAO_DESCRICAO } from '../constants.js';
import { carregarOpcoes, rotuloDe } from '../opcoes.js';
import { criarCartaoDenuncia, rotuloVisao } from '../components/denuncia-card.js';

export const titulo = 'Área da equipe';

const CHAVE_TOKEN = 'acessacidade.tokenEquipe';
const LIMITE = 10;
const EXIGEM_OBSERVACAO = ['ENCAMINHADA', 'RESOLVIDA'];

function lerToken() {
  try {
    return window.sessionStorage.getItem(CHAVE_TOKEN) || '';
  } catch {
    return '';
  }
}
function salvarToken(valor) {
  try {
    if (valor) window.sessionStorage.setItem(CHAVE_TOKEN, valor);
    else window.sessionStorage.removeItem(CHAVE_TOKEN);
    return true;
  } catch {
    return false;
  }
}

export async function render({ container, signal }) {
  container.append(
    el(
      'div',
      { class: 'cabecalho-pagina' },
      el('h1', { tabindex: '-1', text: 'Área da equipe: revisão das denúncias' }),
      el(
        'p',
        {},
        'Pessoas da equipe revisam o resultado da triagem automática e atualizam o status. Cada mudança fica registrada no histórico público da denúncia.',
      ),
    ),
  );
  const opcoes = await carregarOpcoes();
  if (signal.aborted) return;

  // memória do token apenas durante esta visita (se o sessionStorage estiver bloqueado)
  let tokenMemoria = lerToken();

  // ---------- token ----------
  const campoToken = el('input', {
    type: 'password',
    id: 'revisao-token',
    name: 'token',
    autocomplete: 'off',
    spellcheck: 'false',
    'aria-describedby': 'revisao-token-dica',
  });
  const estadoToken = el('p', { class: 'status-inline', role: 'status', id: 'revisao-token-estado' });
  function atualizarEstadoToken() {
    estadoToken.className = tokenMemoria ? 'status-inline status-inline--ok' : 'status-inline';
    estadoToken.textContent = tokenMemoria ? 'Token informado e guardado somente nesta aba.' : 'Nenhum token informado.';
  }
  const formToken = el(
    'form',
    { class: 'secao', id: 'form-token', novalidate: true, 'aria-labelledby': 'titulo-token' },
    el('h2', { id: 'titulo-token', text: 'Token da equipe' }),
    criarAviso(
      'alerta',
      'Cuidado com o token',
      'O token fica guardado apenas nesta aba do navegador (sessionStorage) e é apagado quando a aba é fechada. Não compartilhe o token e não use computadores públicos.',
    ),
    el(
      'div',
      { class: 'campo' },
      el('label', { for: 'revisao-token', text: 'Token de acesso da equipe' }),
      el('span', { class: 'dica', id: 'revisao-token-dica', text: 'Fornecido pela pessoa responsável pela implantação do sistema (variável ADMIN_TOKEN do servidor).' }),
      campoToken,
    ),
    el(
      'div',
      { class: 'acoes' },
      el('button', { type: 'submit', class: 'botao' }, 'Usar este token'),
      el('button', { type: 'button', class: 'botao botao--secundario', id: 'revisao-esquecer-token' }, 'Esquecer token'),
    ),
    estadoToken,
  );
  formToken.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const valor = campoToken.value.trim();
    if (!valor) {
      estadoToken.className = 'status-inline status-inline--erro';
      estadoToken.textContent = 'Digite o token antes de salvar.';
      focar(campoToken, { rolar: false });
      return;
    }
    tokenMemoria = valor;
    salvarToken(valor);
    campoToken.value = '';
    atualizarEstadoToken();
  });
  formToken.querySelector('#revisao-esquecer-token').addEventListener('click', () => {
    tokenMemoria = '';
    salvarToken('');
    campoToken.value = '';
    atualizarEstadoToken();
  });
  atualizarEstadoToken();

  // ---------- lista ----------
  let filtroStatus = 'AGUARDANDO_REVISAO';
  let pagina = 1;
  const selFiltro = el('select', { id: 'revisao-filtro-status', name: 'status' });
  selFiltro.appendChild(el('option', { value: '', text: 'Todos os status' }));
  for (const s of opcoes.status) selFiltro.appendChild(el('option', { value: s.chave, text: s.rotulo }));
  selFiltro.value = filtroStatus;
  const areaLista = el('div', { class: 'pilha', id: 'revisao-lista' });
  const tituloLista = el('h2', { id: 'titulo-lista-revisao', tabindex: '-1', text: 'Denúncias para revisar' });
  const secaoLista = el(
    'section',
    { class: 'pilha', 'aria-labelledby': 'titulo-lista-revisao' },
    tituloLista,
    el('div', { class: 'campo' }, el('label', { for: 'revisao-filtro-status', text: 'Mostrar denúncias com status' }), selFiltro),
    areaLista,
  );

  // ---------- painel de revisão ----------
  const painel = el('section', { class: 'secao', id: 'painel-revisao', hidden: true, 'aria-labelledby': 'titulo-painel-revisao' });

  container.append(formToken, painel, secaoLista);

  selFiltro.addEventListener('change', () => {
    filtroStatus = selFiltro.value;
    pagina = 1;
    carregarLista();
  });

  async function carregarLista({ moverFoco = false } = {}) {
    areaLista.setAttribute('aria-busy', 'true');
    areaLista.replaceChildren(criarCarregando('Carregando denúncias...'));
    try {
      const r = await api.listarDenuncias({ status: filtroStatus, pagina, limite: LIMITE, incluir_simulados: 'true' }, signal);
      if (signal.aborted) return;
      const itens = Array.isArray(r.itens) ? r.itens : [];
      const total = Number(r.total) || 0;
      const totalPaginas = Math.max(1, Math.ceil(total / (Number(r.limite) || LIMITE)));
      const resumo = total
        ? `${formatarNumero(total)} ${total === 1 ? 'denúncia' : 'denúncias'}. Página ${pagina} de ${totalPaginas}.`
        : 'Nenhuma denúncia com este status.';
      const anterior = el('button', { type: 'button', class: 'botao botao--secundario', disabled: pagina <= 1 }, '← Página anterior');
      const proxima = el('button', { type: 'button', class: 'botao botao--secundario', disabled: pagina >= totalPaginas }, 'Próxima página →');
      anterior.addEventListener('click', () => {
        pagina -= 1;
        carregarLista({ moverFoco: true });
      });
      proxima.addEventListener('click', () => {
        pagina += 1;
        carregarLista({ moverFoco: true });
      });
      const botaoRevisar = (d) =>
        el(
          'button',
          { type: 'button', class: 'botao botao--compacto', on: { click: () => abrirPainel(d) } },
          'Revisar',
          el('span', { class: 'sr-only', text: ` a denúncia ${d.protocolo}` }),
        );
      areaLista.replaceChildren(
        el('p', { class: 'paginacao__info', text: resumo }),
        itens.length
          ? el('ul', { class: 'lista-cartoes' }, itens.map((d) => el('li', {}, criarCartaoDenuncia(d, { nivel: 3, acoes: [botaoRevisar(d)] }))))
          : el('p', { class: 'texto-secundario', text: 'Nada para revisar com este filtro.' }),
      );
      if (total > LIMITE) {
        areaLista.appendChild(el('nav', { class: 'paginacao', 'aria-label': 'Paginação da revisão' }, anterior, el('p', { class: 'paginacao__info', text: `Página ${pagina} de ${totalPaginas}` }), proxima));
      }
      if (moverFoco) focar(tituloLista);
    } catch (erro) {
      if (erro instanceof ApiError && erro.tipo === 'cancelado') return;
      areaLista.replaceChildren(criarErroCarregamento(erro, () => carregarLista(), 'Não foi possível carregar a lista'));
    } finally {
      areaLista.removeAttribute('aria-busy');
    }
  }

  function miniatura(visao, etapa, rotulo) {
    const src = visao && visao.imagens ? urlImagemSegura(visao.imagens[etapa]) : null;
    if (!src) return null;
    return el('figure', { class: 'etapa' }, el('img', { src, alt: `${rotulo} da foto enviada`, loading: 'lazy' }), el('figcaption', { text: rotulo }));
  }

  function abrirPainel(d) {
    const tituloPainel = el('h2', { id: 'titulo-painel-revisao', tabindex: '-1', text: `Revisar denúncia ${d.protocolo}` });
    const selStatus = el('select', { id: 'revisao-status', name: 'status', 'aria-describedby': 'revisao-status-dica' });
    for (const s of opcoes.status) selStatus.appendChild(el('option', { value: s.chave, text: s.rotulo }));
    selStatus.value = d.status;
    const observacao = el('textarea', { id: 'revisao-observacao', name: 'observacao', rows: '3', maxlength: '500', 'aria-describedby': 'revisao-observacao-dica' });
    const erroObs = el('p', { class: 'campo-erro', id: 'revisao-observacao-erro', hidden: true });
    const radios = [
      { valor: '', rotulo: 'Manter como está', id: 'revisao-humana-manter' },
      { valor: 'CONFIRMADO', rotulo: 'Confirmado: o problema aparece na foto', id: 'revisao-humana-confirmado' },
      { valor: 'DESCARTADO', rotulo: 'Descartado: o resultado da triagem não se confirma', id: 'revisao-humana-descartado' },
    ];
    const grupoRadios = el(
      'fieldset',
      { 'aria-describedby': 'revisao-humana-atual' },
      el('legend', { text: 'Revisão humana da triagem' }),
      el('p', { class: 'dica', id: 'revisao-humana-atual', text: `Situação atual: ${d.revisao_humana ? REVISAO_DESCRICAO[d.revisao_humana] || d.revisao_humana : 'não revisada.'}` }),
      el(
        'div',
        { class: 'opcoes-radio' },
        radios.map((r) =>
          el(
            'div',
            { class: 'campo-check' },
            el('input', { type: 'radio', name: 'revisao_humana', id: r.id, value: r.valor, checked: r.valor === '' }),
            el('label', { for: r.id, text: r.rotulo }),
          ),
        ),
      ),
    );
    const resultadoEnvio = el('div', { id: 'revisao-resultado', tabindex: '-1', hidden: true });
    const botaoSalvar = el('button', { type: 'submit', class: 'botao', id: 'revisao-salvar' }, 'Salvar alteração');
    const visao = rotuloVisao(d);

    const form = el(
      'form',
      { id: 'form-revisao', novalidate: true },
      el(
        'div',
        { class: 'campo' },
        el('label', { for: 'revisao-status', text: 'Novo status' }),
        el('span', { class: 'dica', id: 'revisao-status-dica', text: 'Encaminhada e Resolvida exigem observação. "Resolvida" é um registro da equipe, não confirmação de órgão público.' }),
        selStatus,
      ),
      el(
        'div',
        { class: 'campo' },
        el('label', { for: 'revisao-observacao' }, 'Observação ', el('span', { class: 'opcional', text: '(obrigatória para Encaminhada e Resolvida)' })),
        el('span', { class: 'dica', id: 'revisao-observacao-dica', text: 'Aparece no histórico público. Não escreva dados pessoais.' }),
        observacao,
        erroObs,
      ),
      grupoRadios,
      el(
        'div',
        { class: 'acoes' },
        botaoSalvar,
        el('button', { type: 'button', class: 'botao botao--secundario', id: 'revisao-cancelar', on: { click: fecharPainel } }, 'Fechar'),
      ),
    );

    painel.replaceChildren(
      tituloPainel,
      el(
        'div',
        { class: 'selos' },
        criarSeloStatus(d.status, d.status_rotulo || rotuloDe('status', d.status)),
        criarSeloVisao(visao.chave, visao.rotulo),
      ),
      el('p', {}, el('a', { href: hrefDenuncia(d.protocolo), target: '_blank', rel: 'noopener' }, 'Abrir detalhes completos e todas as etapas da análise (nova aba)')),
      d.visao ? el('div', { class: 'grade grade--2' }, miniatura(d.visao, 'original', 'Foto original'), miniatura(d.visao, 'contornos', 'Regiões candidatas')) : null,
      form,
      resultadoEnvio,
    );
    painel.hidden = false;
    focar(tituloPainel);

    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      resultadoEnvio.hidden = true;
      erroObs.hidden = true;
      observacao.removeAttribute('aria-invalid');
      observacao.setAttribute('aria-describedby', 'revisao-observacao-dica');
      const status = selStatus.value;
      const obs = observacao.value.trim();
      if (EXIGEM_OBSERVACAO.includes(status) && !obs) {
        erroObs.textContent = `Escreva uma observação: o status "${rotuloDe('status', status)}" exige uma explicação.`;
        erroObs.hidden = false;
        observacao.setAttribute('aria-invalid', 'true');
        observacao.setAttribute('aria-describedby', 'revisao-observacao-dica revisao-observacao-erro');
        focar(observacao, { rolar: false });
        return;
      }
      if (!tokenMemoria) {
        mostrarResultado('erro', 'Token não informado', 'Informe o token da equipe no topo desta página antes de salvar.');
        return;
      }
      const corpo = { status };
      if (obs) corpo.observacao = obs;
      const escolhido = form.querySelector('input[name="revisao_humana"]:checked');
      if (escolhido && escolhido.value) corpo.revisao_humana = escolhido.value;

      botaoSalvar.disabled = true;
      botaoSalvar.textContent = 'Salvando...';
      try {
        const atualizada = await api.atualizarStatus(d.id, corpo, tokenMemoria, signal);
        if (signal.aborted) return;
        mostrarResultado(
          'sucesso',
          'Alteração salva',
          `A denúncia ${atualizada.protocolo || d.protocolo} agora está com status "${atualizada.status_rotulo || rotuloDe('status', atualizada.status)}".`,
        );
        anunciar('Alteração salva.');
        carregarLista();
      } catch (erro) {
        if (erro instanceof ApiError && erro.tipo === 'cancelado') return;
        if (erro instanceof ApiError && erro.status === 401) {
          mostrarResultado('erro', 'Token inválido', 'O servidor não aceitou o token. Confira o token com a pessoa responsável e informe-o novamente.');
        } else if (erro instanceof ApiError && erro.status === 403) {
          mostrarResultado(
            'erro',
            'Revisão desativada neste servidor',
            'A alteração de status está desativada neste ambiente porque o servidor não tem um token da equipe configurado (ADMIN_TOKEN vazio). Peça à pessoa responsável pela implantação para configurá-lo.',
          );
        } else if (erro instanceof ApiError && erro.status === 422 && erro.detalhes.length) {
          mostrarResultado(
            'erro',
            'Dados inválidos',
            erro.detalhes.map((x) => (x.campo ? `${NOMES_CAMPOS[x.campo] || x.campo}: ${x.mensagem}` : x.mensagem)).join(' '),
          );
        } else {
          mostrarResultado('erro', 'Não foi possível salvar', erro.message);
        }
      } finally {
        botaoSalvar.disabled = false;
        botaoSalvar.textContent = 'Salvar alteração';
      }
    });

    function mostrarResultado(tipo, tituloMsg, texto) {
      resultadoEnvio.replaceChildren(criarAviso(tipo, tituloMsg, texto));
      resultadoEnvio.hidden = false;
      focar(resultadoEnvio);
    }
  }

  function fecharPainel() {
    painel.hidden = true;
    painel.replaceChildren();
    focar(tituloLista);
  }

  carregarLista();
}
