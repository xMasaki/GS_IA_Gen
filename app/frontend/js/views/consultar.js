// Tela Consultar (#/consultar) — GET /api/denuncias com filtros e paginação.
import { api, ApiError } from '../api.js';
import { el, anunciar, focar, criarCarregando, criarErroCarregamento, formatarNumero } from '../ui.js';
import { PROTOCOLO_REGEX } from '../constants.js';
import { carregarOpcoes } from '../opcoes.js';
import { criarListaCartoes } from '../components/denuncia-card.js';

export const titulo = 'Consultar denúncias';

const LIMITE = 12;

function selectComOpcoes(id, nome, lista, valor, textoTodos) {
  const s = el('select', { id, name: nome });
  s.appendChild(el('option', { value: '', text: textoTodos }));
  for (const item of lista) s.appendChild(el('option', { value: item.chave, text: item.rotulo }));
  s.value = valor || '';
  return s;
}

export async function render({ container, consulta, signal }) {
  const h1 = el('h1', { tabindex: '-1', text: 'Consultar denúncias' });
  container.append(
    el(
      'div',
      { class: 'cabecalho-pagina' },
      h1,
      el('p', {}, 'Busque pelo número do protocolo ou use os filtros para ver as denúncias registradas. As mais recentes aparecem primeiro.'),
    ),
  );

  const opcoes = await carregarOpcoes();
  if (signal.aborted) return;

  const filtros = {
    status: consulta.get('status') || '',
    tipo_obstaculo: consulta.get('tipo_obstaculo') || '',
    bairro: consulta.get('bairro') || '',
    incluir_simulados: consulta.get('incluir_simulados') !== 'false',
    pagina: Math.max(1, Number.parseInt(consulta.get('pagina') || '1', 10) || 1),
  };

  // ---- busca por protocolo ----
  const campoProtocolo = el('input', {
    type: 'search',
    id: 'busca-protocolo',
    name: 'protocolo',
    autocomplete: 'off',
    spellcheck: 'false',
    placeholder: 'AC-2026-000012',
    maxlength: '20',
    'aria-describedby': 'busca-protocolo-dica',
  });
  const erroProtocolo = el('p', { class: 'campo-erro', id: 'busca-protocolo-erro', hidden: true });
  const formProtocolo = el(
    'form',
    { class: 'secao', role: 'search', 'aria-labelledby': 'titulo-busca', novalidate: true },
    el('h2', { id: 'titulo-busca', text: 'Buscar por protocolo' }),
    el(
      'div',
      { class: 'campo' },
      el('label', { for: 'busca-protocolo', text: 'Número do protocolo' }),
      el('span', { class: 'dica', id: 'busca-protocolo-dica', text: 'Formato: AC-2026-000012 (você recebe este número ao registrar).' }),
      campoProtocolo,
      erroProtocolo,
    ),
    el('div', { class: 'acoes' }, el('button', { type: 'submit', class: 'botao' }, 'Buscar protocolo')),
  );
  formProtocolo.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const valor = campoProtocolo.value.trim().toUpperCase();
    if (!PROTOCOLO_REGEX.test(valor)) {
      erroProtocolo.textContent = valor ? 'Protocolo em formato inválido. Use o formato AC-2026-000012.' : 'Digite o número do protocolo.';
      erroProtocolo.hidden = false;
      campoProtocolo.setAttribute('aria-invalid', 'true');
      campoProtocolo.setAttribute('aria-describedby', 'busca-protocolo-dica busca-protocolo-erro');
      focar(campoProtocolo, { rolar: false });
      return;
    }
    window.location.hash = `#/denuncia/${encodeURIComponent(valor)}`;
  });

  // ---- filtros ----
  const selStatus = selectComOpcoes('filtro-status', 'status', opcoes.status, filtros.status, 'Todos os status');
  const selTipo = selectComOpcoes('filtro-tipo', 'tipo_obstaculo', opcoes.tipo_obstaculo, filtros.tipo_obstaculo, 'Todos os tipos');
  const campoBairro = el('input', { type: 'text', id: 'filtro-bairro', name: 'bairro', value: filtros.bairro, maxlength: '80', autocomplete: 'off' });
  const chkSimulados = el('input', { type: 'checkbox', id: 'filtro-simulados', name: 'incluir_simulados', checked: filtros.incluir_simulados });
  const formFiltros = el(
    'form',
    { class: 'secao', 'aria-labelledby': 'titulo-filtros', novalidate: true },
    el('h2', { id: 'titulo-filtros', text: 'Filtrar denúncias' }),
    el(
      'div',
      { class: 'filtros' },
      el('div', { class: 'campo' }, el('label', { for: 'filtro-status', text: 'Status' }), selStatus),
      el('div', { class: 'campo' }, el('label', { for: 'filtro-tipo', text: 'Tipo de obstáculo' }), selTipo),
      el('div', { class: 'campo' }, el('label', { for: 'filtro-bairro', text: 'Bairro (contém)' }), campoBairro),
      el('div', { class: 'campo-check' }, chkSimulados, el('label', { for: 'filtro-simulados', text: 'Incluir dados simulados (demonstração)' })),
    ),
    el(
      'div',
      { class: 'acoes' },
      el('button', { type: 'submit', class: 'botao' }, 'Aplicar filtros'),
      el('button', { type: 'button', class: 'botao botao--secundario', id: 'filtro-limpar' }, 'Limpar filtros'),
    ),
  );

  const tituloResultados = el('h2', { id: 'titulo-resultados', tabindex: '-1', text: 'Resultados' });
  const areaResultados = el('div', { class: 'pilha', id: 'resultados-consulta' });
  const secaoResultados = el('section', { 'aria-labelledby': 'titulo-resultados' }, tituloResultados, areaResultados);
  container.append(formProtocolo, formFiltros, secaoResultados);

  function atualizarUrl() {
    const p = new URLSearchParams();
    if (filtros.status) p.set('status', filtros.status);
    if (filtros.tipo_obstaculo) p.set('tipo_obstaculo', filtros.tipo_obstaculo);
    if (filtros.bairro) p.set('bairro', filtros.bairro);
    if (!filtros.incluir_simulados) p.set('incluir_simulados', 'false');
    if (filtros.pagina > 1) p.set('pagina', String(filtros.pagina));
    const qs = p.toString();
    history.replaceState(null, '', `#/consultar${qs ? `?${qs}` : ''}`);
  }

  async function carregar({ moverFoco = false } = {}) {
    areaResultados.setAttribute('aria-busy', 'true');
    areaResultados.replaceChildren(criarCarregando('Buscando denúncias...'));
    try {
      const r = await api.listarDenuncias(
        {
          status: filtros.status,
          tipo_obstaculo: filtros.tipo_obstaculo,
          bairro: filtros.bairro,
          incluir_simulados: filtros.incluir_simulados ? 'true' : 'false',
          pagina: filtros.pagina,
          limite: LIMITE,
        },
        signal,
      );
      if (signal.aborted) return;
      areaResultados.removeAttribute('aria-busy');
      const itens = Array.isArray(r.itens) ? r.itens : [];
      const total = Number(r.total) || 0;
      const limite = Number(r.limite) || LIMITE;
      const pagina = Number(r.pagina) || filtros.pagina;
      const totalPaginas = Math.max(1, Math.ceil(total / limite));
      const resumo = total
        ? `${formatarNumero(total)} ${total === 1 ? 'denúncia encontrada' : 'denúncias encontradas'}. Página ${pagina} de ${totalPaginas}.`
        : 'Nenhuma denúncia encontrada com esses filtros.';

      const botaoAnterior = el('button', { type: 'button', class: 'botao botao--secundario', id: 'pagina-anterior', disabled: pagina <= 1 }, '← Página anterior');
      const botaoProxima = el('button', { type: 'button', class: 'botao botao--secundario', id: 'pagina-proxima', disabled: pagina >= totalPaginas }, 'Próxima página →');
      botaoAnterior.addEventListener('click', () => {
        filtros.pagina = Math.max(1, pagina - 1);
        atualizarUrl();
        carregar({ moverFoco: true });
      });
      botaoProxima.addEventListener('click', () => {
        filtros.pagina = pagina + 1;
        atualizarUrl();
        carregar({ moverFoco: true });
      });

      areaResultados.replaceChildren(
        el('p', { class: 'paginacao__info', text: resumo }),
        itens.length ? criarListaCartoes(itens, { nivel: 3 }) : el('p', {}, 'Tente outros filtros ou ', el('a', { href: '#/registrar', text: 'registre uma nova denúncia' }), '.'),
        total > limite ? el('nav', { class: 'paginacao', 'aria-label': 'Paginação dos resultados' }, botaoAnterior, el('p', { class: 'paginacao__info', text: `Página ${pagina} de ${totalPaginas}` }), botaoProxima) : null,
      );
      anunciar(resumo);
      if (moverFoco) focar(tituloResultados);
    } catch (erro) {
      if (erro instanceof ApiError && erro.tipo === 'cancelado') return;
      areaResultados.removeAttribute('aria-busy');
      areaResultados.replaceChildren(criarErroCarregamento(erro, () => carregar(), 'Não foi possível buscar as denúncias'));
    }
  }

  formFiltros.addEventListener('submit', (ev) => {
    ev.preventDefault();
    filtros.status = selStatus.value;
    filtros.tipo_obstaculo = selTipo.value;
    filtros.bairro = campoBairro.value.trim();
    filtros.incluir_simulados = chkSimulados.checked;
    filtros.pagina = 1;
    atualizarUrl();
    carregar({ moverFoco: true });
  });
  formFiltros.querySelector('#filtro-limpar').addEventListener('click', () => {
    selStatus.value = '';
    selTipo.value = '';
    campoBairro.value = '';
    chkSimulados.checked = true;
    Object.assign(filtros, { status: '', tipo_obstaculo: '', bairro: '', incluir_simulados: true, pagina: 1 });
    atualizarUrl();
    carregar({ moverFoco: true });
  });

  carregar();
}
