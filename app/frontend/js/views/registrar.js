// Tela Registrar denúncia (#/registrar). Ids/names/data-rpa EXATOS do contrato (seção 7).
import { api, ApiError, NOMES_CAMPOS } from '../api.js';
import {
  el,
  anunciar,
  focar,
  criarAviso,
  criarCarregando,
  criarSeloStatus,
  criarSeloVisao,
  formatarNumero,
  formatarTamanhoArquivo,
  hrefDenuncia,
} from '../ui.js';
import { AVISO_TRIAGEM, LIMITES, TIPOS_IMAGEM_ACEITOS, ROTULO_SEM_FOTO } from '../constants.js';
import { carregarOpcoes } from '../opcoes.js';

export const titulo = 'Registrar denúncia';

/** Validação no cliente espelhando o contrato 4.2. Retorna [{campo, mensagem}]. */
export function validarDenuncia(v, { foto = null, maxUploadMb = 5, chavesTipo = [], chavesImpacto = [] } = {}) {
  const erros = [];
  const tam = (s) => (s || '').length;
  const add = (campo, mensagem) => erros.push({ campo, mensagem });

  if (tam(v.nome) > LIMITES.nome.max) add('nome', `Use no máximo ${LIMITES.nome.max} caracteres.`);
  if (!v.logradouro) add('logradouro', 'Informe o logradouro (nome da rua, avenida ou praça).');
  else if (tam(v.logradouro) < LIMITES.logradouro.min || tam(v.logradouro) > LIMITES.logradouro.max)
    add('logradouro', `O logradouro deve ter entre ${LIMITES.logradouro.min} e ${LIMITES.logradouro.max} caracteres.`);
  if (tam(v.numero) > LIMITES.numero.max) add('numero', `Use no máximo ${LIMITES.numero.max} caracteres (ex.: 120 ou S/N).`);
  if (!v.bairro) add('bairro', 'Informe o bairro.');
  else if (tam(v.bairro) < LIMITES.bairro.min || tam(v.bairro) > LIMITES.bairro.max)
    add('bairro', `O bairro deve ter entre ${LIMITES.bairro.min} e ${LIMITES.bairro.max} caracteres.`);
  if (tam(v.cidade) > LIMITES.cidade.max) add('cidade', `Use no máximo ${LIMITES.cidade.max} caracteres.`);
  if (tam(v.ponto_referencia) > LIMITES.ponto_referencia.max)
    add('ponto_referencia', `Use no máximo ${LIMITES.ponto_referencia.max} caracteres.`);
  if (!v.tipo_obstaculo) add('tipo_obstaculo', 'Escolha o tipo de obstáculo.');
  else if (chavesTipo.length && !chavesTipo.includes(v.tipo_obstaculo)) add('tipo_obstaculo', 'Escolha uma opção da lista.');
  if (!v.descricao) add('descricao', 'Descreva o problema.');
  else if (tam(v.descricao) < LIMITES.descricao.min || tam(v.descricao) > LIMITES.descricao.max)
    add('descricao', `A descrição deve ter entre ${LIMITES.descricao.min} e ${LIMITES.descricao.max} caracteres (agora tem ${tam(v.descricao)}).`);
  if (!v.impacto) add('impacto', 'Escolha o impacto do problema.');
  else if (chavesImpacto.length && !chavesImpacto.includes(v.impacto)) add('impacto', 'Escolha uma opção da lista.');

  const temLat = v.latitude !== '';
  const temLon = v.longitude !== '';
  if (temLat !== temLon) {
    add(temLat ? 'longitude' : 'latitude', 'Informe latitude e longitude juntas, ou deixe as duas em branco.');
  }
  if (temLat) {
    const lat = Number(v.latitude);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90) add('latitude', 'A latitude deve ser um número entre -90 e 90 (ex.: -23.5505).');
  }
  if (temLon) {
    const lon = Number(v.longitude);
    if (!Number.isFinite(lon) || lon < -180 || lon > 180) add('longitude', 'A longitude deve ser um número entre -180 e 180 (ex.: -46.6333).');
  }
  const erroFoto = validarFoto(foto, maxUploadMb);
  if (erroFoto) add('foto', erroFoto);
  if (!v.consentimento) add('consentimento', 'Para enviar, marque que você leu e concorda com o uso da foto e dos dados.');
  return erros;
}

/** Valida tipo e tamanho da foto. Retorna a mensagem de erro ou null. */
export function validarFoto(foto, maxUploadMb = 5) {
  if (!foto) return null;
  if (foto.type && !TIPOS_IMAGEM_ACEITOS.includes(foto.type)) return 'Formato não aceito. Envie uma foto JPEG, PNG ou WEBP.';
  if (foto.size === 0) return 'O arquivo da foto está vazio.';
  if (foto.size > maxUploadMb * 1024 * 1024) return `A foto tem ${formatarTamanhoArquivo(foto.size)}. O limite é ${formatarNumero(maxUploadMb)} MB.`;
  return null;
}

/** "−23,55" -> "-23.55" (aceita vírgula decimal). */
function normalizarNumero(texto) {
  return String(texto || '')
    .trim()
    .replace(/−/g, '-')
    .replace(',', '.');
}

function criarCampo({ id, nome, rotulo, obrigatorio = false, dica, controle }) {
  const idDica = dica ? `${id}-dica` : null;
  const idErro = `${id}-erro`;
  controle.id = id;
  controle.setAttribute('name', nome);
  controle.setAttribute('data-rpa', nome);
  if (idDica) controle.setAttribute('aria-describedby', idDica);
  if (obrigatorio) controle.setAttribute('aria-required', 'true');
  const erro = el('p', { class: 'campo-erro', id: idErro, hidden: true });
  const wrapper = el(
    'div',
    { class: 'campo' },
    el(
      'label',
      { for: id },
      rotulo,
      ' ',
      obrigatorio ? el('span', { class: 'obrigatorio', text: '(obrigatório)' }) : el('span', { class: 'opcional', text: '(opcional)' }),
    ),
    dica ? el('span', { class: 'dica', id: idDica }, dica) : null,
    controle,
    erro,
  );
  return { wrapper, controle, erro, idDica };
}

function input(attrs) {
  return el('input', { type: 'text', ...attrs });
}

function criarSelect(lista) {
  const s = el('select', {});
  s.appendChild(el('option', { value: '', text: 'Selecione uma opção' }));
  for (const item of lista) s.appendChild(el('option', { value: item.chave, text: item.rotulo }));
  return s;
}

export async function render({ container, consulta, signal }) {
  const canalRpa = (consulta.get('canal') || '').toLowerCase() === 'rpa';
  const h1 = el('h1', { tabindex: '-1', text: 'Registrar denúncia' });
  container.append(
    el(
      'div',
      { class: 'cabecalho-pagina' },
      h1,
      el(
        'p',
        {},
        'Conte onde está o problema de acessibilidade e como ele atrapalha a passagem. Campos marcados como "(obrigatório)" precisam ser preenchidos. Leva cerca de 3 minutos.',
      ),
      canalRpa ? el('p', {}, el('span', { class: 'selo selo--neutro', text: 'Canal: automação (RPA)' }), ' Este envio será registrado com origem RPA.') : null,
    ),
  );
  const carregando = criarCarregando('Carregando o formulário...');
  container.append(carregando);

  const opcoes = await carregarOpcoes();
  if (signal.aborted) return undefined;
  carregando.remove();

  // ---------- campos ----------
  const campos = {};
  const registrar = (nome, campo) => {
    campos[nome] = campo;
    return campo.wrapper;
  };

  const fNome = registrar(
    'nome',
    criarCampo({
      id: 'campo-nome',
      nome: 'nome',
      rotulo: 'Seu nome ou apelido',
      dica: 'Pode ser um apelido. Seu nome nunca aparece publicamente nem é enviado para outros sistemas.',
      controle: input({ maxlength: String(LIMITES.nome.max), autocomplete: 'nickname' }),
    }),
  );
  const fLogradouro = registrar(
    'logradouro',
    criarCampo({
      id: 'campo-logradouro',
      nome: 'logradouro',
      rotulo: 'Logradouro',
      obrigatorio: true,
      dica: 'Rua, avenida ou praça. Exemplo: Rua Exemplo.',
      controle: input({ maxlength: String(LIMITES.logradouro.max), autocomplete: 'address-line1' }),
    }),
  );
  const fNumero = registrar(
    'numero',
    criarCampo({
      id: 'campo-numero',
      nome: 'numero',
      rotulo: 'Número',
      dica: 'Número mais próximo. Exemplo: 120 ou S/N.',
      controle: input({ maxlength: String(LIMITES.numero.max), autocomplete: 'off' }),
    }),
  );
  const fBairro = registrar(
    'bairro',
    criarCampo({
      id: 'campo-bairro',
      nome: 'bairro',
      rotulo: 'Bairro',
      obrigatorio: true,
      controle: input({ maxlength: String(LIMITES.bairro.max), autocomplete: 'address-level3' }),
    }),
  );
  const fCidade = registrar(
    'cidade',
    criarCampo({
      id: 'campo-cidade',
      nome: 'cidade',
      rotulo: 'Cidade',
      dica: 'Se ficar em branco, o sistema usa a cidade padrão configurada.',
      controle: input({ maxlength: String(LIMITES.cidade.max), autocomplete: 'address-level2' }),
    }),
  );
  const fReferencia = registrar(
    'ponto_referencia',
    criarCampo({
      id: 'campo-referencia',
      nome: 'ponto_referencia',
      rotulo: 'Ponto de referência',
      dica: 'Exemplo: em frente ao ponto de ônibus, ao lado da padaria.',
      controle: input({ maxlength: String(LIMITES.ponto_referencia.max), autocomplete: 'off' }),
    }),
  );
  const fTipo = registrar(
    'tipo_obstaculo',
    criarCampo({ id: 'campo-tipo', nome: 'tipo_obstaculo', rotulo: 'Tipo de obstáculo', obrigatorio: true, controle: criarSelect(opcoes.tipo_obstaculo) }),
  );
  const contadorDescricao = el('span', { class: 'contador', id: 'campo-descricao-contador', text: `0 de ${LIMITES.descricao.max} caracteres` });
  const campoDescricao = criarCampo({
    id: 'campo-descricao',
    nome: 'descricao',
    rotulo: 'Descrição do problema',
    obrigatorio: true,
    dica: [
      `De ${LIMITES.descricao.min} a ${LIMITES.descricao.max} caracteres. Diga o que é, o tamanho aproximado e quem é prejudicado. `,
      el('a', { href: '#/assistente?modo=descricao&contexto=registro', target: '_blank', rel: 'noopener' }, 'Peça ajuda ao assistente para escrever (abre em nova aba)'),
    ],
    controle: el('textarea', { rows: '5', maxlength: String(LIMITES.descricao.max) }),
  });
  campoDescricao.controle.setAttribute('aria-describedby', 'campo-descricao-dica campo-descricao-contador');
  campoDescricao.wrapper.insertBefore(contadorDescricao, campoDescricao.erro);
  const fDescricao = registrar('descricao', campoDescricao);
  const fImpacto = registrar(
    'impacto',
    criarCampo({
      id: 'campo-impacto',
      nome: 'impacto',
      rotulo: 'Impacto para quem passa',
      obrigatorio: true,
      controle: criarSelect(opcoes.impacto),
    }),
  );
  const fLat = registrar(
    'latitude',
    criarCampo({
      id: 'campo-latitude',
      nome: 'latitude',
      rotulo: 'Latitude',
      dica: 'Exemplo: -23.5505',
      controle: input({ inputmode: 'decimal', autocomplete: 'off', maxlength: '20' }),
    }),
  );
  const fLon = registrar(
    'longitude',
    criarCampo({
      id: 'campo-longitude',
      nome: 'longitude',
      rotulo: 'Longitude',
      dica: 'Exemplo: -46.6333',
      controle: input({ inputmode: 'decimal', autocomplete: 'off', maxlength: '20' }),
    }),
  );
  const estadoLocalizacao = el('p', { class: 'status-inline', id: 'estado-localizacao', role: 'status' });
  const botaoLocalizacao = el('button', { type: 'button', class: 'botao botao--secundario', id: 'botao-localizacao' }, 'Usar minha localização');

  const fFoto = registrar(
    'foto',
    criarCampo({
      id: 'campo-foto',
      nome: 'foto',
      rotulo: 'Fotografia do problema',
      dica: `JPEG, PNG ou WEBP, até ${formatarNumero(opcoes.max_upload_mb)} MB. Evite mostrar rostos e placas de veículos. Antes de salvar, removemos dados escondidos da foto (como localização GPS) e borramos rostos detectados.`,
      controle: el('input', { type: 'file', accept: 'image/jpeg,image/png,image/webp' }),
    }),
  );
  const previa = el('div', { class: 'previa-foto', id: 'previa-foto', hidden: true });

  const consentimento = el('input', {
    type: 'checkbox',
    id: 'campo-consentimento',
    name: 'consentimento',
    'data-rpa': 'consentimento',
    value: 'true',
    'aria-required': 'true',
    'aria-describedby': 'campo-consentimento-texto',
  });
  const erroConsentimento = el('p', { class: 'campo-erro', id: 'campo-consentimento-erro', hidden: true });
  campos.consentimento = { controle: consentimento, erro: erroConsentimento, idDica: 'campo-consentimento-texto' };

  const botaoEnviar = el('button', { type: 'submit', class: 'botao botao--grande', id: 'botao-enviar' }, 'Enviar denúncia');

  const form = el(
    'form',
    { id: 'form-denuncia', novalidate: true, 'aria-labelledby': 'titulo-form' },
    el('h2', { id: 'titulo-form', class: 'sr-only', text: 'Formulário de denúncia' }),
    el('fieldset', {}, el('legend', { text: 'Identificação' }), fNome),
    el(
      'fieldset',
      {},
      el('legend', { text: 'Onde está o problema' }),
      el('div', { class: 'linha-campos' }, fLogradouro, fNumero),
      el('div', { class: 'linha-campos' }, fBairro, fCidade),
      fReferencia,
    ),
    el('fieldset', {}, el('legend', { text: 'O que é o problema' }), el('div', { class: 'linha-campos' }, fTipo, fImpacto), fDescricao),
    el(
      'fieldset',
      {},
      el('legend', { text: 'Localização no mapa (opcional)' }),
      el('p', { class: 'dica', text: 'Se você estiver no local, pode usar a localização do aparelho. Ela só é usada nesta denúncia.' }),
      el('div', { class: 'linha-campos linha-campos--estreito' }, fLat, fLon),
      el('div', { class: 'campo' }, botaoLocalizacao, estadoLocalizacao),
    ),
    el('fieldset', {}, el('legend', { text: 'Fotografia (opcional)' }), fFoto, previa),
    el(
      'div',
      { class: 'campo' },
      el(
        'div',
        { class: 'campo-check' },
        consentimento,
        el(
          'div',
          {},
          el(
            'label',
            { for: 'campo-consentimento' },
            el('strong', { text: 'Li e concordo com o uso da foto e dos dados ' }),
            el('span', { class: 'obrigatorio', text: '(obrigatório)' }),
          ),
          el(
            'ul',
            { class: 'dica', id: 'campo-consentimento-texto' },
            el('li', { text: 'Sempre que possível, a foto não mostra rostos nem placas de veículos.' }),
            el('li', { text: 'Os dados serão usados somente para registrar, analisar e acompanhar esta denúncia.' }),
            el('li', { text: 'A foto passa por uma triagem automática, que é revisada por uma pessoa da equipe.' }),
          ),
          el('a', { href: '#/sobre', target: '_blank', rel: 'noopener' }, 'Leia a política de privacidade (abre em nova aba)'),
        ),
      ),
      erroConsentimento,
    ),
    el('div', { class: 'acoes' }, botaoEnviar),
    el('p', { class: 'status-inline', id: 'estado-envio', role: 'status' }),
  );

  // Caixa de erro (validação no cliente e respostas 4xx/5xx)
  const erroEnvio = el('div', {
    id: 'erro-envio',
    class: 'aviso aviso--erro',
    tabindex: '-1',
    hidden: true,
    'aria-labelledby': 'erro-envio-titulo',
  });

  // Caixa de sucesso
  const protocoloGerado = el('strong', { id: 'protocolo-gerado', class: 'protocolo' });
  const resumoResultado = el('div', { id: 'resumo-resultado' });
  const linkDetalhe = el('a', { class: 'botao', id: 'link-detalhe-denuncia', href: '#/consultar' }, 'Ver detalhes e análise da foto');
  const botaoNova = el('button', { type: 'button', class: 'botao botao--secundario', id: 'botao-nova-denuncia' }, 'Registrar outra denúncia');
  const tituloResultado = el('h2', { id: 'resultado-envio-titulo', tabindex: '-1', text: 'Denúncia registrada com sucesso' });
  const resultadoEnvio = el(
    'section',
    { id: 'resultado-envio', class: 'secao resultado-envio', hidden: true, 'aria-labelledby': 'resultado-envio-titulo' },
    tituloResultado,
    el('p', {}, 'Anote o número do protocolo para acompanhar a denúncia:'),
    el('p', {}, protocoloGerado),
    resumoResultado,
    el('div', { class: 'acoes' }, linkDetalhe, botaoNova),
  );

  container.append(erroEnvio, form, resultadoEnvio);

  // ---------- comportamento ----------
  const estadoEnvio = form.querySelector('#estado-envio');
  let urlPrevia = null;

  function limparPrevia() {
    if (urlPrevia) URL.revokeObjectURL(urlPrevia);
    urlPrevia = null;
    previa.replaceChildren();
    previa.hidden = true;
  }

  function definirErroCampo(nome, mensagem) {
    const c = campos[nome];
    if (!c) return;
    const describedby = [c.idDica, nome === 'descricao' ? 'campo-descricao-contador' : null].filter(Boolean);
    if (mensagem) {
      c.erro.textContent = mensagem;
      c.erro.hidden = false;
      c.controle.setAttribute('aria-invalid', 'true');
      describedby.push(c.erro.id);
    } else {
      c.erro.textContent = '';
      c.erro.hidden = true;
      c.controle.removeAttribute('aria-invalid');
    }
    if (describedby.length) c.controle.setAttribute('aria-describedby', describedby.join(' '));
  }

  function limparErros() {
    Object.keys(campos).forEach((n) => definirErroCampo(n, ''));
    erroEnvio.hidden = true;
    erroEnvio.replaceChildren();
  }

  function mostrarErroEnvio(titulo, itens, textoExtra) {
    const lista = el(
      'ul',
      {},
      itens.map((item) => {
        const c = item.campo && campos[item.campo];
        const texto = item.campo ? `${NOMES_CAMPOS[item.campo] || item.campo}: ${item.mensagem}` : item.mensagem;
        if (!c) return el('li', { text: texto });
        return el(
          'li',
          {},
          el(
            'a',
            {
              href: `#${c.controle.id}`,
              on: {
                click: (ev) => {
                  ev.preventDefault();
                  focar(c.controle);
                },
              },
            },
            texto,
          ),
        );
      }),
    );
    erroEnvio.replaceChildren(
      el('h2', { class: 'aviso__titulo', id: 'erro-envio-titulo', text: titulo }),
      textoExtra ? el('p', { text: textoExtra }) : null,
      itens.length ? lista : null,
    );
    erroEnvio.hidden = false;
    focar(erroEnvio);
  }

  function lerValores() {
    const val = (n) => (campos[n].controle.value || '').trim();
    return {
      nome: val('nome'),
      logradouro: val('logradouro'),
      numero: val('numero'),
      bairro: val('bairro'),
      cidade: val('cidade'),
      ponto_referencia: val('ponto_referencia'),
      tipo_obstaculo: val('tipo_obstaculo'),
      descricao: val('descricao'),
      impacto: val('impacto'),
      latitude: normalizarNumero(campos.latitude.controle.value),
      longitude: normalizarNumero(campos.longitude.controle.value),
      consentimento: consentimento.checked,
    };
  }

  function mostrarSucesso(d) {
    form.hidden = true;
    erroEnvio.hidden = true;
    protocoloGerado.textContent = d.protocolo;
    linkDetalhe.setAttribute('href', hrefDenuncia(d.protocolo));
    const visao = d.visao;
    resumoResultado.replaceChildren(
      d.mensagem ? el('p', { text: d.mensagem }) : null,
      el('p', {}, 'Situação atual: ', criarSeloStatus(d.status, d.status_rotulo)),
      visao
        ? el(
            'div',
            {},
            el('h3', { text: 'Resultado da triagem automática da foto' }),
            el('p', {}, criarSeloVisao(visao.classificacao, visao.rotulo)),
            Number.isFinite(Number(visao.pontuacao))
              ? el('p', { text: `Pontuação heurística: ${formatarNumero(Number(visao.pontuacao), 2)} de 1 (não é uma probabilidade).` })
              : null,
            Array.isArray(visao.explicacao) && visao.explicacao.length ? el('p', { class: 'texto-secundario', text: String(visao.explicacao[0]) }) : null,
            criarAviso('alerta', null, visao.aviso || AVISO_TRIAGEM),
          )
        : el('p', {}, criarSeloVisao(null, ROTULO_SEM_FOTO), ' Sem fotografia: não houve triagem automática.'),
    );
    resultadoEnvio.hidden = false;
    focar(tituloResultado);
    anunciar(`Denúncia registrada. Protocolo ${d.protocolo}.`);
  }

  function novaDenuncia() {
    form.reset();
    limparPrevia();
    limparErros();
    contadorDescricao.textContent = `0 de ${LIMITES.descricao.max} caracteres`;
    estadoLocalizacao.textContent = '';
    estadoEnvio.textContent = '';
    resultadoEnvio.hidden = true;
    protocoloGerado.textContent = '';
    resumoResultado.replaceChildren();
    form.hidden = false;
    focar(campos.nome.controle);
  }

  let enviando = false;
  async function enviar(ev) {
    ev.preventDefault();
    if (enviando) return;
    limparErros();
    const valores = lerValores();
    const foto = campos.foto.controle.files && campos.foto.controle.files[0] ? campos.foto.controle.files[0] : null;
    const erros = validarDenuncia(valores, {
      foto,
      maxUploadMb: opcoes.max_upload_mb,
      chavesTipo: opcoes.tipo_obstaculo.map((o) => o.chave),
      chavesImpacto: opcoes.impacto.map((o) => o.chave),
    });
    if (erros.length) {
      erros.forEach((e) => definirErroCampo(e.campo, e.mensagem));
      mostrarErroEnvio(
        erros.length === 1 ? 'Corrija 1 campo para enviar' : `Corrija ${erros.length} campos para enviar`,
        erros,
        'Selecione um item da lista para ir direto ao campo.',
      );
      return;
    }

    const fd = new FormData();
    for (const campo of ['nome', 'logradouro', 'numero', 'bairro', 'cidade', 'ponto_referencia', 'tipo_obstaculo', 'descricao', 'impacto']) {
      if (valores[campo]) fd.append(campo, valores[campo]);
    }
    if (valores.latitude !== '' && valores.longitude !== '') {
      fd.append('latitude', valores.latitude);
      fd.append('longitude', valores.longitude);
    }
    fd.append('consentimento', 'true');
    fd.append('origem', canalRpa ? 'RPA' : 'WEB');
    if (foto) fd.append('foto', foto, foto.name || 'foto');

    enviando = true;
    botaoEnviar.disabled = true;
    botaoEnviar.textContent = foto ? 'Enviando e analisando a foto...' : 'Enviando a denúncia...';
    form.setAttribute('aria-busy', 'true');
    estadoEnvio.textContent = foto ? 'Enviando e analisando a foto. Isso pode levar alguns segundos.' : 'Enviando a denúncia...';
    try {
      const resposta = await api.criarDenuncia(fd, signal);
      if (signal.aborted) return;
      estadoEnvio.textContent = '';
      mostrarSucesso(resposta);
    } catch (erro) {
      if (erro instanceof ApiError && erro.tipo === 'cancelado') return;
      estadoEnvio.textContent = '';
      const detalhes = erro instanceof ApiError ? erro.detalhes : [];
      const status = erro instanceof ApiError ? erro.status : 0;
      if (status === 422 && detalhes.length) {
        detalhes.forEach((d) => d.campo && definirErroCampo(d.campo, d.mensagem));
        mostrarErroEnvio('Alguns dados precisam ser corrigidos', detalhes, 'O servidor não aceitou o envio pelos motivos abaixo.');
      } else if (status === 429) {
        mostrarErroEnvio('Muitas tentativas em pouco tempo', [], erro.message);
      } else {
        mostrarErroEnvio('Não foi possível enviar a denúncia', [], `${erro.message} Seus dados continuam preenchidos no formulário.`);
      }
    } finally {
      enviando = false;
      botaoEnviar.disabled = false;
      botaoEnviar.textContent = 'Enviar denúncia';
      form.removeAttribute('aria-busy');
    }
  }

  form.addEventListener('submit', enviar);
  botaoNova.addEventListener('click', novaDenuncia);

  campoDescricao.controle.addEventListener('input', () => {
    contadorDescricao.textContent = `${campoDescricao.controle.value.length} de ${LIMITES.descricao.max} caracteres`;
  });

  campos.foto.controle.addEventListener('change', () => {
    limparPrevia();
    definirErroCampo('foto', '');
    const arquivo = campos.foto.controle.files && campos.foto.controle.files[0];
    if (!arquivo) return;
    const problema = validarFoto(arquivo, opcoes.max_upload_mb);
    if (problema) {
      definirErroCampo('foto', problema);
      return;
    }
    urlPrevia = URL.createObjectURL(arquivo);
    previa.replaceChildren(
      el('img', { src: urlPrevia, alt: 'Prévia da foto selecionada' }),
      el('p', { text: `${arquivo.name} — ${formatarTamanhoArquivo(arquivo.size)}` }),
      el(
        'button',
        {
          type: 'button',
          class: 'botao botao--secundario botao--compacto',
          on: {
            click: () => {
              campos.foto.controle.value = '';
              limparPrevia();
              anunciar('Foto removida.');
              focar(campos.foto.controle, { rolar: false });
            },
          },
        },
        'Remover foto',
      ),
    );
    previa.hidden = false;
  });

  botaoLocalizacao.addEventListener('click', () => {
    estadoLocalizacao.className = 'status-inline';
    if (!('geolocation' in navigator)) {
      estadoLocalizacao.className = 'status-inline status-inline--erro';
      estadoLocalizacao.textContent = 'Seu navegador não oferece localização. Você pode deixar estes campos em branco.';
      return;
    }
    botaoLocalizacao.disabled = true;
    estadoLocalizacao.textContent = 'Obtendo sua localização...';
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        botaoLocalizacao.disabled = false;
        campos.latitude.controle.value = pos.coords.latitude.toFixed(6);
        campos.longitude.controle.value = pos.coords.longitude.toFixed(6);
        definirErroCampo('latitude', '');
        definirErroCampo('longitude', '');
        estadoLocalizacao.className = 'status-inline status-inline--ok';
        estadoLocalizacao.textContent = `Localização preenchida (precisão aproximada de ${formatarNumero(pos.coords.accuracy, 0)} metros).`;
      },
      (erro) => {
        botaoLocalizacao.disabled = false;
        estadoLocalizacao.className = 'status-inline status-inline--erro';
        const mensagens = {
          1: 'Você não permitiu o acesso à localização. Tudo bem: os campos são opcionais.',
          2: 'Não foi possível descobrir sua localização agora. Os campos são opcionais.',
          3: 'A localização demorou demais. Tente de novo ou deixe os campos em branco.',
        };
        estadoLocalizacao.textContent = mensagens[erro && erro.code] || 'Não foi possível obter a localização. Os campos são opcionais.';
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  });

  return () => limparPrevia();
}
