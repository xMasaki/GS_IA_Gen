// Tela "Testar análise de foto" (#/analise) — POST /api/visao/analisar (não salva nada).
import { api, ApiError } from '../api.js';
import { el, anunciar, focar, criarAviso, formatarTamanhoArquivo } from '../ui.js';
import { carregarOpcoes } from '../opcoes.js';
import { renderizarAnaliseVisao } from '../components/vision-analysis.js';
import { validarFoto } from './registrar.js';

export const titulo = 'Testar análise de foto';

export function render({ container, signal }) {
  container.append(
    el(
      'div',
      { class: 'cabecalho-pagina' },
      el('h1', { tabindex: '-1', text: 'Testar a análise de uma foto' }),
      el(
        'p',
        {},
        'Envie uma foto de calçada para ver, passo a passo, como a triagem automática funciona. ',
        el('strong', { text: 'Nada é salvo e nenhuma denúncia é criada.' }),
        ' Para registrar um problema, use a página ',
        el('a', { href: '#/registrar', text: 'Registrar denúncia' }),
        '.',
      ),
    ),
  );

  const campoFoto = el('input', {
    type: 'file',
    id: 'analise-foto',
    name: 'foto',
    accept: 'image/jpeg,image/png,image/webp',
    'aria-describedby': 'analise-foto-dica',
    'aria-required': 'true',
  });
  const erroFoto = el('p', { class: 'campo-erro', id: 'analise-foto-erro', hidden: true });
  const previa = el('div', { class: 'previa-foto', hidden: true });
  const botao = el('button', { type: 'submit', class: 'botao botao--grande', id: 'analise-enviar' }, 'Analisar foto');
  const estado = el('p', { class: 'status-inline', role: 'status', id: 'analise-estado' });
  const resultado = el('section', { class: 'secao', id: 'analise-resultado', 'aria-labelledby': 'analise-resultado-titulo', hidden: true });
  let urlPrevia = null;

  function erroCampo(msg) {
    if (msg) {
      erroFoto.textContent = msg;
      erroFoto.hidden = false;
      campoFoto.setAttribute('aria-invalid', 'true');
      campoFoto.setAttribute('aria-describedby', 'analise-foto-dica analise-foto-erro');
    } else {
      erroFoto.hidden = true;
      campoFoto.removeAttribute('aria-invalid');
      campoFoto.setAttribute('aria-describedby', 'analise-foto-dica');
    }
  }

  function limparPrevia() {
    if (urlPrevia) URL.revokeObjectURL(urlPrevia);
    urlPrevia = null;
    previa.replaceChildren();
    previa.hidden = true;
  }

  const form = el(
    'form',
    { class: 'secao', id: 'form-analise', novalidate: true, 'aria-labelledby': 'titulo-form-analise' },
    el('h2', { id: 'titulo-form-analise', text: 'Escolha a foto' }),
    el(
      'div',
      { class: 'campo' },
      el('label', { for: 'analise-foto' }, 'Fotografia ', el('span', { class: 'obrigatorio', text: '(obrigatório)' })),
      el('span', { class: 'dica', id: 'analise-foto-dica', text: 'JPEG, PNG ou WEBP. Prefira fotos tiradas de cima, com boa luz e sem pessoas.' }),
      campoFoto,
      erroFoto,
      previa,
    ),
    el('div', { class: 'acoes' }, botao),
    estado,
  );
  container.append(form, resultado);

  campoFoto.addEventListener('change', async () => {
    limparPrevia();
    erroCampo('');
    const arquivo = campoFoto.files && campoFoto.files[0];
    if (!arquivo) return;
    const opcoes = await carregarOpcoes();
    const problema = validarFoto(arquivo, opcoes.max_upload_mb);
    if (problema) {
      erroCampo(problema);
      return;
    }
    urlPrevia = URL.createObjectURL(arquivo);
    previa.replaceChildren(
      el('img', { src: urlPrevia, alt: 'Prévia da foto selecionada' }),
      el('p', { text: `${arquivo.name} — ${formatarTamanhoArquivo(arquivo.size)}` }),
    );
    previa.hidden = false;
  });

  let enviando = false;
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if (enviando) return;
    const arquivo = campoFoto.files && campoFoto.files[0];
    const opcoes = await carregarOpcoes();
    const problema = arquivo ? validarFoto(arquivo, opcoes.max_upload_mb) : 'Escolha uma foto para analisar.';
    if (problema) {
      erroCampo(problema);
      focar(campoFoto, { rolar: false });
      return;
    }
    erroCampo('');
    const fd = new FormData();
    fd.append('foto', arquivo, arquivo.name || 'foto');
    enviando = true;
    botao.disabled = true;
    botao.textContent = 'Analisando a foto...';
    estado.textContent = 'Analisando a foto. Isso pode levar alguns segundos.';
    resultado.setAttribute('aria-busy', 'true');
    try {
      const r = await api.analisarFoto(fd, signal);
      if (signal.aborted) return;
      estado.textContent = '';
      const tituloResultado = el('h2', { id: 'analise-resultado-titulo', tabindex: '-1', text: 'Resultado da análise' });
      resultado.replaceChildren(
        tituloResultado,
        renderizarAnaliseVisao(r, { nivel: 3 }),
        el(
          'div',
          { class: 'acoes' },
          el('a', { class: 'botao', href: '#/registrar' }, 'Registrar uma denúncia com esta situação'),
          el('a', { class: 'botao botao--secundario', href: '#/assistente?modo=explicar_resultado&contexto=analise' }, 'Tirar dúvidas com o assistente'),
        ),
      );
      resultado.hidden = false;
      focar(tituloResultado);
      anunciar(`Análise concluída: ${r.rotulo || r.classificacao || ''}.`);
    } catch (erro) {
      if (erro instanceof ApiError && erro.tipo === 'cancelado') return;
      estado.textContent = '';
      const caixa = criarAviso('erro', 'Não foi possível analisar a foto', erro.message);
      caixa.setAttribute('tabindex', '-1');
      resultado.replaceChildren(el('h2', { id: 'analise-resultado-titulo', class: 'sr-only', text: 'Erro na análise' }), caixa);
      resultado.hidden = false;
      focar(caixa);
    } finally {
      enviando = false;
      botao.disabled = false;
      botao.textContent = 'Analisar foto';
      resultado.removeAttribute('aria-busy');
    }
  });

  return () => limparPrevia();
}
