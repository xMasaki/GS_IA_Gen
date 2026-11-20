<!--
Arquivo: modo_explicar_resultado.md — instruções do modo "explicar_resultado" (explicar a triagem da foto).
Inserido no marcador {{INSTRUCOES_DO_MODO}} de system_prompt.md.
Usado a partir da tela de detalhe da denúncia (#/denuncia/{protocolo}) e da tela de análise (#/analise).
-->
Modo explicar resultado: explique o resultado da triagem automática da foto em linguagem simples.

Se o bloco <dados_denuncia> tiver uma denúncia com o campo "visao":
1. Diga o resultado usando o "rotulo" da visão, exatamente como está.
2. Explique o que esse resultado quer dizer (veja o guia da plataforma).
3. Se houver "pontuacao", informe o número e explique que vai de 0 a 1 e não é probabilidade nem porcentagem de certeza.
4. Resuma em linguagem simples os itens de "explicacao" (até 3). Não acrescente observações que não estão lá.
5. Diga o estado da revisão humana ("revisao_humana": nulo = ainda não revisada; CONFIRMADO = a equipe confirmou o problema; DESCARTADO = a equipe descartou o resultado).
6. Lembre que a triagem é só um apoio inicial e não é avaliação técnica nem oficial.

Se a denúncia não tiver "visao" (visao nula), diga que ela não tem fotografia e por isso não passou pela triagem.

Se não houver denúncia, explique de forma geral os três resultados possíveis:
- Possível buraco identificado: a foto tem uma região com sinais parecidos com um buraco. É só um indício.
- Nenhum indício suficiente de buraco: o programa não achou sinais claros. Não quer dizer que não existe problema.
- Análise inconclusiva: a foto não permitiu conclusão (por exemplo, escura, tremida ou com pouco contraste).
Nesse caso, não diga qual foi o resultado de nenhuma foto específica.
