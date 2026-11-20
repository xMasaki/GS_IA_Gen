<!--
Arquivo: guia_plataforma.md — conhecimento de referência da plataforma AcessaCidade.
Inserido no marcador {{GUIA_PLATAFORMA}} de system_prompt.md.
Fonte: docs/CONTRATOS_DE_INTEGRACAO.md (seções 3, 4, 7 e 11). Ao mudar o contrato, atualize este guia.
Não coloque aqui dados de denúncias, URLs públicas, nomes de pessoas ou números de indicadores:
esses dados chegam em tempo de execução, nos blocos de dados.
-->
## Telas da plataforma

- Início (#/): propósito do AcessaCidade, botão para registrar, indicadores resumidos, denúncias recentes e ODS 11.
- Registrar (#/registrar): formulário para registrar uma denúncia.
- Detalhe da denúncia (#/denuncia/ seguido do protocolo): dados da denúncia, análise da fotografia com todas as etapas e histórico de status.
- Analisar foto (#/analise): testa a triagem de uma foto sem registrar denúncia e sem salvar nada.
- Consultar (#/consultar): lista de denúncias com filtros (status, bairro, tipo) e busca por protocolo.
- Assistente (#/assistente): conversa com o AcessaCidade Helper.
- Painel (#/painel): indicadores com totais por bairro, tipo de problema, status, resultado da triagem e origem.
- Área da equipe (#/revisao): uso exclusivo da equipe, com token, para revisar denúncias e mudar o status.
- Sobre (#/sobre): propósito, privacidade e LGPD, limites da triagem e ODS.

## Como registrar uma denúncia (tela Registrar)

Campos do formulário:
- Nome: opcional (até 80 caracteres). Pode ser apelido. Nunca aparece para outras pessoas nem nas exportações.
- Logradouro (nome da rua): obrigatório (3 a 120 caracteres).
- Número: opcional (até 10 caracteres, por exemplo "120" ou "S/N").
- Bairro: obrigatório (2 a 80 caracteres).
- Cidade: opcional (até 80 caracteres).
- Ponto de referência: opcional (até 150 caracteres).
- Tipo de obstáculo: obrigatório (lista de opções).
- Descrição: obrigatória (10 a 1000 caracteres).
- Impacto: obrigatório (lista de opções).
- Latitude e longitude: opcionais; informe as duas ou nenhuma.
- Fotografia: opcional; JPEG, PNG ou WEBP, até o limite de tamanho mostrado na tela.
- Consentimento: obrigatório; a pessoa precisa aceitar os termos de uso da foto e dos dados.
Depois de enviar, a tela mostra o número de protocolo e um link para a página da denúncia. Há um botão para registrar outra denúncia.

## Protocolo

Formato AC-AAAA-NNNNNN: "AC", o ano com 4 dígitos e um número com 6 dígitos, separados por hífen. Serve para consultar a denúncia na tela Consultar ou na página da denúncia.

## Status e como mudam

- Toda denúncia começa como "Recebida".
- Se houver foto, a triagem automática roda e o status muda sozinho para "Aguardando revisão".
- As outras mudanças ("Em análise", "Encaminhada", "Resolvida") são feitas só pela equipe do AcessaCidade, na Área da equipe.
- "Encaminhada" e "Resolvida" sempre têm uma observação da equipe no histórico.
- "Resolvida" é um registro da equipe. Não é confirmação de prefeitura ou de órgão público.

## Triagem automática da foto (visão computacional)

- Usa processamento de imagem clássico (OpenCV), sem redes neurais. Roda no servidor do AcessaCidade.
- Etapas mostradas na página da denúncia: original, cinza, filtrada, contraste, bordas, máscara e contornos.
- Resultados possíveis: "Possível buraco identificado", "Nenhum indício suficiente de buraco" ou "Análise inconclusiva". Sem foto: "Sem fotografia (não analisada)".
- A pontuação vai de 0 a 1. É uma pontuação heurística: não é probabilidade nem porcentagem de certeza.
- A triagem procura sinais de buraco. Ela pode não reconhecer outros problemas, como rampa irregular, piso tátil danificado ou obstáculos.
- Fotos escuras, tremidas, de longe ou com sombras fortes podem gerar resultado errado ou inconclusivo.
- É apoio inicial, não decisão. Uma pessoa da equipe revisa: "revisão humana" pode ser "confirmado" (problema confirmado na foto) ou "descartado".

## Privacidade e LGPD

- O nome é opcional, fica guardado só no banco do sistema e nunca é mostrado, exportado ou enviado ao assistente.
- A foto é tratada antes de ser salva: o sistema refaz o arquivo (apagando metadados, como a localização GPS), reduz o tamanho e tenta borrar rostos automaticamente. A detecção de rostos pode falhar.
- As exportações para análise de dados não têm o nome de quem denunciou.
- Recomende não escrever telefone, CPF, e-mail ou endereço de casa na descrição.
- Quando o assistente usa um modelo de IA, a pergunta e os dados públicos da denúncia são enviados a um provedor externo de IA (via OpenRouter). Por isso, a pessoa não deve enviar dados pessoais no chat.
- Algumas denúncias são de demonstração e estão marcadas como dados simulados.

## ODS 11

O AcessaCidade se conecta ao Objetivo de Desenvolvimento Sustentável 11 da ONU (Cidades e comunidades sustentáveis), em especial à meta 11.7: acesso universal a espaços públicos seguros, inclusivos e acessíveis, em particular para pessoas idosas e pessoas com deficiência.

## O que o AcessaCidade não faz

- Não é serviço oficial do governo e não substitui os canais oficiais da prefeitura.
- Não garante conserto nem prazo.
- Não diz se uma rota é acessível ou segura.
- Não atende emergências (SAMU 192, Bombeiros 193).
