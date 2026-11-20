// Constantes e enumerações de reserva (fallback) — idênticas ao contrato
// docs/CONTRATOS_DE_INTEGRACAO.md, seção 3. Usadas quando GET /api/meta/opcoes falha.

export const APP_NOME = 'AcessaCidade';

export const PROTOCOLO_REGEX = /^AC-\d{4}-\d{6}$/;

/** Ordem oficial das etapas da triagem (contrato 4.1 / 5). */
export const ETAPAS = ['original', 'cinza', 'filtrada', 'contraste', 'bordas', 'mascara', 'contornos'];

export const AVISO_TRIAGEM =
  'Triagem automática inicial. Não substitui avaliação técnica; requer revisão humana.';

export const MAX_UPLOAD_MB_PADRAO = 5;
export const TIPOS_IMAGEM_ACEITOS = ['image/jpeg', 'image/png', 'image/webp'];

/** Limites dos campos do formulário (contrato 4.2). */
export const LIMITES = {
  nome: { max: 80 },
  logradouro: { min: 3, max: 120 },
  numero: { max: 10 },
  bairro: { min: 2, max: 80 },
  cidade: { max: 80 },
  ponto_referencia: { max: 150 },
  descricao: { min: 10, max: 1000 },
  mensagemAssistente: { min: 1, max: 1000 },
};

export const OPCOES_PADRAO = Object.freeze({
  tipo_obstaculo: [
    { chave: 'BURACO_CALCADA', rotulo: 'Buraco na calçada' },
    { chave: 'BURACO_VIA', rotulo: 'Buraco na via ou travessia' },
    { chave: 'CALCADA_DANIFICADA', rotulo: 'Calçada quebrada ou desnivelada' },
    { chave: 'RAMPA_IRREGULAR', rotulo: 'Rampa ausente ou irregular' },
    { chave: 'PISO_TATIL', rotulo: 'Piso tátil ausente ou danificado' },
    { chave: 'OBSTACULO_FIXO', rotulo: 'Obstáculo fixo (poste, lixeira, placa)' },
    { chave: 'OBSTACULO_TEMPORARIO', rotulo: 'Obstáculo temporário (entulho, veículo, obra)' },
    { chave: 'OUTRO', rotulo: 'Outro' },
  ],
  impacto: [
    { chave: 'IMPEDE_PASSAGEM', rotulo: 'Impede a passagem' },
    { chave: 'DIFICULTA_PASSAGEM', rotulo: 'Dificulta a passagem' },
    { chave: 'RISCO_QUEDA', rotulo: 'Risco de queda ou acidente' },
    { chave: 'BAIXO_IMPACTO', rotulo: 'Baixo impacto' },
  ],
  status: [
    { chave: 'RECEBIDA', rotulo: 'Recebida', significado: 'A denúncia foi registrada no AcessaCidade.' },
    { chave: 'EM_ANALISE', rotulo: 'Em análise', significado: 'A equipe do AcessaCidade está verificando as informações.' },
    {
      chave: 'AGUARDANDO_REVISAO',
      rotulo: 'Aguardando revisão',
      significado: 'A triagem automática da foto terminou e uma pessoa precisa revisar o resultado.',
    },
    {
      chave: 'ENCAMINHADA',
      rotulo: 'Encaminhada',
      significado: 'A equipe registrou que a ocorrência foi encaminhada ao responsável.',
    },
    {
      chave: 'RESOLVIDA',
      rotulo: 'Resolvida',
      significado: 'A equipe registrou a ocorrência como resolvida. Não representa confirmação de órgão público.',
    },
  ],
  classificacao_visao: [
    { chave: 'POSSIBLE_POTHOLE', rotulo: 'Possível buraco identificado' },
    { chave: 'NOT_IDENTIFIED', rotulo: 'Nenhum indício suficiente de buraco' },
    { chave: 'INCONCLUSIVE', rotulo: 'Análise inconclusiva' },
  ],
  origem: [
    { chave: 'WEB', rotulo: 'WEB' },
    { chave: 'RPA', rotulo: 'RPA' },
    { chave: 'SIMULADO', rotulo: 'SIMULADO' },
    { chave: 'API', rotulo: 'API' },
  ],
  revisao_humana: [
    { chave: 'CONFIRMADO', rotulo: 'Confirmado' },
    { chave: 'DESCARTADO', rotulo: 'Descartado' },
  ],
});

export const ROTULO_SEM_FOTO = 'Sem fotografia (não analisada)';

/** Descrição amigável de cada origem (contrato 3.5). */
export const ORIGEM_DESCRICAO = {
  WEB: 'Formulário web',
  RPA: 'Robô de automação (RPA)',
  SIMULADO: 'Dado simulado (demonstração)',
  API: 'Chamada direta à API',
};

/** Texto amigável da revisão humana (contrato 3.6). */
export const REVISAO_DESCRICAO = {
  CONFIRMADO: 'Confirmado: uma pessoa da equipe confirmou o problema na foto.',
  DESCARTADO: 'Descartado: uma pessoa da equipe descartou o resultado da triagem.',
};

/** Modos do assistente (contrato 4.9). */
export const MODOS_ASSISTENTE = [
  { chave: 'geral', rotulo: 'Dúvida geral' },
  { chave: 'descricao', rotulo: 'Ajuda para escrever a descrição' },
  { chave: 'explicar_resultado', rotulo: 'Explicar resultado da análise' },
];

/** Legendas das etapas da triagem, na ordem de ETAPAS. */
export const LEGENDAS_ETAPAS = {
  original: {
    titulo: 'Foto original (tratada)',
    texto:
      'É a foto enviada depois do tratamento de privacidade: metadados como localização GPS (EXIF) removidos, tamanho reduzido e rostos borrados quando detectados.',
  },
  cinza: {
    titulo: 'Escala de cinza',
    texto: 'As cores são removidas. O algoritmo passa a comparar apenas o quanto cada ponto é claro ou escuro.',
  },
  filtrada: {
    titulo: 'Imagem filtrada (suavizada)',
    texto: 'Um filtro de suavização reduz ruídos e texturas finas do piso, preservando as formas maiores.',
  },
  contraste: {
    titulo: 'Contraste realçado',
    texto: 'O contraste é ajustado para destacar a diferença entre áreas claras e escuras, como a sombra dentro de um buraco.',
  },
  bordas: {
    titulo: 'Bordas detectadas',
    texto: 'Linhas brancas marcam os lugares onde a luminosidade muda de forma brusca, como as beiradas de um buraco ou de uma rachadura.',
  },
  mascara: {
    titulo: 'Máscara de regiões escuras',
    texto: 'Em branco aparecem as áreas escuras que podem ser buracos; em preto, o que foi descartado.',
  },
  contornos: {
    titulo: 'Contornos e regiões candidatas',
    texto: 'As áreas que atenderam aos critérios do algoritmo (tamanho e formato) são desenhadas sobre a foto.',
  },
};

/** Nomes amigáveis para métricas conhecidas (as demais aparecem com o nome técnico). */
export const NOMES_METRICAS = {
  brilho_medio: 'Brilho médio',
  brilho: 'Brilho médio',
  contraste: 'Contraste',
  contraste_rms: 'Contraste',
  nitidez: 'Nitidez',
  nitidez_laplaciano: 'Nitidez (variância do Laplaciano)',
  area_escura_percentual: 'Área escura (% da imagem)',
  area_percentual: 'Área candidata (% da imagem)',
  area_maior_regiao_percentual: 'Maior região candidata (% da imagem)',
  densidade_bordas: 'Densidade de bordas',
  densidade_bordas_percentual: 'Densidade de bordas (%)',
  num_contornos: 'Número de contornos',
  num_regioes: 'Número de regiões candidatas',
  regioes_candidatas: 'Regiões candidatas',
  largura: 'Largura da imagem (px)',
  altura: 'Altura da imagem (px)',
  largura_px: 'Largura da imagem (px)',
  altura_px: 'Altura da imagem (px)',
  tempo_ms: 'Tempo de processamento (ms)',
  rostos_borrados: 'Rostos borrados',
  percentual_pixels_escuros: 'Pixels muito escuros (% da imagem)',
  percentual_pixels_saturados: 'Pixels estourados/brancos (% da imagem)',
  percentual_mascara: 'Regiões escuras candidatas (% da imagem)',
  densidade_bordas_global: 'Densidade de bordas na imagem (0 a 1)',
  num_candidatas: 'Regiões candidatas analisadas',
  num_deteccoes: 'Regiões destacadas como possível buraco',
  qualidade_adequada: 'Qualidade da foto adequada',
  problemas_qualidade: 'Problemas de qualidade da foto',
  largura_original: 'Largura original (px)',
  altura_original: 'Altura original (px)',
  largura_analise: 'Largura usada na análise (px)',
  altura_analise: 'Altura usada na análise (px)',
  histograma_16_faixas: 'Histograma de brilho (16 faixas)',
  histograma_bimodal_extenso: 'Histograma bimodal extenso',
  fracao_escura_otsu: 'Fração escura (limiar de Otsu)',
  mediana_cinza: 'Mediana do brilho',
  sigma_robusto: 'Desvio robusto do brilho',
  limiar_otsu: 'Limiar de Otsu',
  efetividade_otsu: 'Efetividade do limiar de Otsu',
  limiar_robusto: 'Limiar robusto',
  limiar_aplicado: 'Limiar aplicado',
  decisao: 'Regra de decisão aplicada',
  candidatas: 'Regiões candidatas (dados técnicos)',
  parametros: 'Parâmetros',
  coordenadas_referem_se_a: 'Coordenadas referem-se a',
};

/** Nome da tela atual enviado ao assistente como contexto_tela. */
export const CONTEXTO_TELA = {
  '/': 'inicio',
  '/registrar': 'registro',
  '/denuncia': 'detalhe',
  '/analise': 'analise',
  '/consultar': 'consulta',
  '/assistente': 'assistente',
  '/painel': 'painel',
  '/revisao': 'revisao',
  '/sobre': 'sobre',
};
