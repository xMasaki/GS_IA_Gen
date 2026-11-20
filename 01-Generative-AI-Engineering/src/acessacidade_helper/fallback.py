"""Modo alternativo (sem LLM): respostas por regras e intenções, em português simples.

É usado quando não há chave de API, quando a API falha e quando a resposta do LLM é
descartada pelos guardrails. Nunca inventa dados: só usa o texto da pessoa, a denúncia
fornecida pelo backend, os indicadores fornecidos e as regras do contrato.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from . import domain
from .context import ContextoPreparado
from .guardrails import (
    AVISO_NAO_OFICIAL,
    AVISO_SIMULADO,
    AVISO_TRIAGEM,
    normalizar,
    remover_dados_pessoais,
)

FORMATO_PROTOCOLO = "AC-AAAA-NNNNNN: as letras AC, o ano com 4 números e mais 6 números, separados por hífen"


@dataclass
class RespostaRegras:
    resposta: str
    intencao: str
    avisos: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Detecção de intenção (palavras-chave sobre texto normalizado: minúsculo, sem acento)
# ---------------------------------------------------------------------------
INTENCOES: dict[str, dict[str, float]] = {
    "emergencia": {
        "emergencia": 3, "machuc": 3, "ferid": 3, "sangr": 3, "socorro": 3, "samu": 3,
        "ambulancia": 3, "desmai": 3,
    },
    "registrar": {
        "registrar": 2, "registro": 1, "denunciar": 2, "fazer uma denuncia": 2, "fazer denuncia": 2,
        "nova denuncia": 2, "abrir denuncia": 2, "reportar": 2, "cadastrar": 2, "formulario": 1.5,
        "enviar foto": 1, "como envio": 1.5, "como faco para avisar": 2, "avisar sobre": 1,
    },
    "status": {
        "status": 2, "situacao": 1.5, "recebida": 2, "em analise": 2, "aguardando revisao": 2,
        "encaminhada": 2, "resolvida": 2, "significa": 0.5, "quer dizer": 0.5, "etapas": 1,
    },
    "triagem": {
        "triagem": 2.5, "visao computacional": 2.5, "classificacao": 1.5, "possivel buraco": 2.5,
        "inconclusiv": 2.5, "nenhum indicio": 2.5, "nao identificad": 2, "pontuacao": 2,
        "analise da foto": 2.5, "analisar foto": 2, "analisar a foto": 2, "algoritmo": 1.5,
        "foto": 0.75, "imagem": 0.75, "resultado": 1,
    },
    "protocolo": {
        "protocolo": 2, "acompanhar": 2, "minha denuncia": 2, "consultar": 1.5, "andamento": 2,
        "ac-": 1,
    },
    "descricao": {
        "descricao": 2, "descrever": 2, "escrever": 1.5, "redigir": 2, "texto da denuncia": 2,
    },
    "privacidade": {
        "privacidade": 3, "lgpd": 3, "dados pessoais": 3, "meu nome": 2, "anonim": 2.5,
        "rosto": 2, "apagar": 1.5, "excluir": 1.5, "quem ve": 1.5, "gps": 2, "cpf": 2,
        "meus dados": 2.5, "seguranca dos dados": 3, "localizacao": 1,
    },
    "ods": {
        "ods": 3, "objetivo de desenvolvimento": 3, "sustentave": 2, "onu": 2, "agenda 2030": 3,
    },
    "oficial": {
        "prefeitura": 2.5, "governo": 2, "orgao": 1.5, "consert": 2, "arrumar": 1.5, "prazo": 2,
        "quando vao": 1.5, "quando vai": 1.5, "oficial": 2, "subprefeitura": 2.5,
    },
    "rota": {
        "rota": 2.5, "caminho": 1.5, "trajeto": 2.5, "posso passar": 3, "da para passar": 3,
        "e seguro": 2, "esta acessivel": 2.5, "e acessivel": 2.5, "rua acessivel": 2.5,
    },
    "indicadores": {
        "quantas": 2, "quantos": 2, "indicador": 2.5, "painel": 2, "estatistic": 2.5,
        "dashboard": 2.5, "numeros": 1.5, "total de denuncias": 2.5,
    },
    "sobre": {
        "o que e o acessacidade": 3, "o que e acessacidade": 3, "quem e voce": 3,
        "o que voce faz": 3, "para que serve": 2, "como voce pode ajudar": 3, "ajuda": 0.5,
    },
}
_SAUDACOES = ("oi", "ola", "bom dia", "boa tarde", "boa noite", "e ai", "hello", "hi")

# Ordem de desempate (mais específico primeiro)
_PRIORIDADE = (
    "emergencia", "rota", "privacidade", "descricao", "triagem", "protocolo", "status",
    "registrar", "oficial", "indicadores", "ods", "sobre",
)


def detectar_intencao(texto: str) -> str:
    n = " " + normalizar(texto) + " "
    n = re.sub(r"[^\w\s%-]", " ", n)
    n = re.sub(r"\s+", " ", n)
    pontos: dict[str, float] = {}
    for intencao, palavras in INTENCOES.items():
        total = 0.0
        for palavra, peso in palavras.items():
            if len(palavra) <= 4 and palavra.isalpha():
                if re.search(rf"\b{re.escape(palavra)}\b", n):
                    total += peso
            elif palavra in n:
                total += peso
        if total:
            pontos[intencao] = total
    if "emergencia" in pontos:
        return "emergencia"
    if not pontos:
        palavras = n.split()
        if palavras and len(palavras) <= 4 and any(
            n.strip().startswith(s) for s in _SAUDACOES
        ):
            return "saudacao"
        return "fora_escopo"
    melhor = max(pontos.values())
    for intencao in _PRIORIDADE:
        if pontos.get(intencao) == melhor:
            return intencao
    return "fora_escopo"


# ---------------------------------------------------------------------------
# Utilidades de formatação
# ---------------------------------------------------------------------------
def _data_br(iso: object) -> str | None:
    if not isinstance(iso, str) or not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.strftime("%d/%m/%Y")


def _pontuacao_br(valor: object) -> str | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return f"{float(valor):.2f}".replace(".", ",")


def _rotulo(mapa: dict, chave: object, rotulo: object = None) -> str:
    if isinstance(rotulo, str) and rotulo:
        return rotulo
    if isinstance(chave, str) and chave in mapa:
        return mapa[chave]
    return "não informado"


def _endereco(d: dict) -> str:
    partes = []
    log = d.get("logradouro")
    if log:
        partes.append(f"{log}, {d['numero']}" if d.get("numero") else str(log))
    for campo in ("bairro", "cidade"):
        if d.get(campo):
            partes.append(str(d[campo]))
    texto = " - ".join(partes) if partes else "endereço não informado"
    if d.get("ponto_referencia"):
        texto += f" (referência: {d['ponto_referencia']})"
    return texto


def _status_mencionados(texto: str) -> list[str]:
    n = normalizar(texto)
    return [k for k, rotulo in domain.STATUS.items() if normalizar(rotulo) in n]


# ---------------------------------------------------------------------------
# Respostas por intenção
# ---------------------------------------------------------------------------
def resposta_sobre() -> str:
    return (
        "Eu sou o AcessaCidade Helper. Posso ajudar você a:\n"
        "- registrar um problema de acessibilidade na calçada ou na rua;\n"
        "- escrever a descrição do problema;\n"
        "- entender o status de uma denúncia;\n"
        "- entender o resultado da triagem automática da foto;\n"
        "- consultar uma denúncia pelo protocolo;\n"
        "- tirar dúvidas sobre privacidade dos seus dados.\n"
        "O que você precisa?"
    )


def resposta_registrar() -> str:
    return (
        "Para registrar um problema, abra a tela \"Registrar\" (#/registrar) e siga os passos:\n"
        "1. Informe o logradouro (nome da rua) e o bairro. São obrigatórios.\n"
        "2. Se souber, informe o número, a cidade e um ponto de referência.\n"
        "3. Escolha o tipo de obstáculo e o impacto.\n"
        "4. Escreva a descrição, com 10 a 1000 caracteres. Posso ajudar nisso.\n"
        "5. Se quiser, envie uma foto (JPEG, PNG ou WEBP). A foto é opcional.\n"
        "6. Marque a caixa de consentimento e toque em \"Enviar\".\n"
        "No fim, você recebe um número de protocolo. Guarde esse número para acompanhar a denúncia.\n"
        "O nome é opcional e nunca aparece para outras pessoas."
    )


def resposta_status(texto: str) -> str:
    mencionados = _status_mencionados(texto)
    if len(mencionados) == 1:
        k = mencionados[0]
        outros = ", ".join(domain.STATUS[o] for o in domain.STATUS if o != k)
        return (
            f"\"{domain.STATUS[k]}\" quer dizer: {domain.STATUS_SIGNIFICADO[k]}\n"
            f"Os outros status são: {outros}.\n"
            "Para ver o status de uma denúncia, informe o protocolo ou use a tela \"Consultar\" (#/consultar)."
        )
    linhas = ["Cada denúncia passa por estes status:"]
    linhas += [f"- {domain.STATUS[k]}: {domain.STATUS_SIGNIFICADO[k]}" for k in domain.STATUS]
    linhas.append(
        "Para ver o status de uma denúncia, informe o protocolo ou use a tela \"Consultar\" (#/consultar)."
    )
    return "\n".join(linhas)


def resposta_triagem_generica() -> str:
    return (
        "Quando você envia uma foto, o AcessaCidade faz uma triagem automática. "
        "O programa trata a imagem (tons de cinza, filtro, contraste, bordas e contornos) "
        "e procura sinais parecidos com um buraco. O resultado pode ser:\n"
        "- Possível buraco identificado: a foto tem uma região com sinais parecidos com um buraco. É só um indício.\n"
        "- Nenhum indício suficiente de buraco: o programa não achou sinais claros. "
        "Isso não quer dizer que não existe problema. Rampas, piso tátil e outros obstáculos, por exemplo, podem não ser reconhecidos.\n"
        "- Análise inconclusiva: a foto não permitiu uma conclusão. Pode estar escura, tremida ou com pouco contraste.\n"
        "A pontuação vai de 0 a 1. Ela não é probabilidade nem porcentagem de certeza.\n"
        "Uma pessoa da equipe sempre pode revisar o resultado. "
        "Você pode testar uma foto sem registrar denúncia na tela \"Analisar foto\" (#/analise)."
    )


def resposta_triagem_denuncia(d: dict) -> str:
    protocolo = d.get("protocolo") or "informada"
    visao = d.get("visao")
    if not isinstance(visao, dict):
        return (
            f"A denúncia {protocolo} não tem fotografia. Por isso, ela não passou pela triagem automática.\n"
            "A equipe analisa a denúncia pelas informações escritas."
        )
    rotulo = _rotulo(domain.CLASSIFICACOES_VISAO, visao.get("classificacao"), visao.get("rotulo"))
    linhas = [f"Resultado da triagem da foto da denúncia {protocolo}: {rotulo}."]
    pont = _pontuacao_br(visao.get("pontuacao"))
    if pont:
        linhas.append(
            f"Pontuação: {pont} (de 0 a 1). Ela não é probabilidade nem porcentagem de certeza."
        )
    explicacao = visao.get("explicacao")
    if isinstance(explicacao, list) and explicacao:
        linhas.append("O que o programa observou na foto:")
        linhas += [f"- {item}" for item in explicacao[:5] if isinstance(item, str) and item]
    classe = visao.get("classificacao")
    if classe == "POSSIBLE_POTHOLE":
        linhas.append("Isso é só um indício. A confirmação depende de revisão humana.")
    elif classe == "NOT_IDENTIFIED":
        linhas.append(
            "Isso não quer dizer que não existe problema. A triagem procura sinais de buraco e pode não reconhecer outros obstáculos."
        )
    elif classe == "INCONCLUSIVE":
        linhas.append("A foto não permitiu uma conclusão. Uma pessoa da equipe vai olhar a denúncia.")
    revisao = d.get("revisao_humana")
    linhas.append(
        f"Revisão humana: {domain.REVISAO_HUMANA.get(revisao if revisao in domain.REVISAO_HUMANA else None)}."
    )
    linhas.append(f"Veja todas as etapas da análise na tela da denúncia (#/denuncia/{protocolo}).")
    return "\n".join(linhas)


def resposta_resumo_denuncia(d: dict) -> str:
    protocolo = d.get("protocolo") or "informada"
    status = d.get("status")
    status_rotulo = _rotulo(domain.STATUS, status, d.get("status_rotulo"))
    linhas = [f"Encontrei a denúncia {protocolo}."]
    linhas.append(f"- Tipo: {_rotulo(domain.TIPOS_OBSTACULO, d.get('tipo_obstaculo'), d.get('tipo_obstaculo_rotulo'))}")
    linhas.append(f"- Local: {_endereco(d)}")
    linhas.append(f"- Impacto: {_rotulo(domain.IMPACTOS, d.get('impacto'), d.get('impacto_rotulo'))}")
    data = _data_br(d.get("criado_em"))
    if data:
        linhas.append(f"- Registrada em: {data}")
    significado = domain.STATUS_SIGNIFICADO.get(status) if isinstance(status, str) else None
    linhas.append(f"- Status atual: {status_rotulo}" + (f". {significado}" if significado else ""))
    visao = d.get("visao")
    if isinstance(visao, dict):
        linhas.append(
            f"- Triagem da foto: {_rotulo(domain.CLASSIFICACOES_VISAO, visao.get('classificacao'), visao.get('rotulo'))}"
        )
    else:
        linhas.append(f"- Triagem da foto: {domain.ROTULO_SEM_FOTO}")
    revisao = d.get("revisao_humana")
    linhas.append(
        f"- Revisão humana: {domain.REVISAO_HUMANA.get(revisao if revisao in domain.REVISAO_HUMANA else None)}"
    )
    historico = d.get("historico")
    if isinstance(historico, list) and historico and isinstance(historico[-1], dict):
        ultimo = historico[-1]
        obs = ultimo.get("observacao")
        quando = _data_br(ultimo.get("alterado_em"))
        if obs:
            linhas.append(f"- Último registro: \"{obs}\"" + (f" em {quando}" if quando else ""))
    linhas.append(f"Veja os detalhes na tela da denúncia (#/denuncia/{protocolo}).")
    return "\n".join(linhas)


def resposta_protocolo_nao_encontrado(protocolo: str) -> str:
    return (
        f"Não encontrei nenhuma denúncia com o protocolo {protocolo}.\n"
        "Confira se o número está certo. O formato é AC-AAAA-NNNNNN, com letras maiúsculas e hífens.\n"
        "Você também pode procurar na tela \"Consultar\" (#/consultar). Eu não invento informações sobre denúncias."
    )


def resposta_protocolo_sem_numero() -> str:
    return (
        "Para consultar uma denúncia, me diga o número do protocolo. "
        f"O formato é {FORMATO_PROTOCOLO}.\n"
        "Você recebe esse número quando termina o registro. "
        "Também dá para procurar pelo bairro ou pelo tipo de problema na tela \"Consultar\" (#/consultar)."
    )


def resposta_privacidade() -> str:
    return (
        "Sobre privacidade (LGPD):\n"
        "- O nome é opcional. Ele fica guardado só no sistema e nunca aparece para outras pessoas nem nas exportações.\n"
        "- A foto é tratada antes de ser salva: o sistema apaga os dados escondidos do arquivo (como a localização GPS) e tenta borrar rostos. "
        "A detecção de rostos pode falhar, então evite fotografar pessoas.\n"
        "- A localização no mapa é opcional.\n"
        "- Não escreva telefone, CPF ou e-mail na descrição.\n"
        "- Quando o assistente usa IA, sua pergunta pode ser processada por um serviço externo de IA. Não envie dados pessoais.\n"
        "Mais detalhes na tela \"Sobre\" (#/sobre)."
    )


def resposta_ods() -> str:
    return (
        "O AcessaCidade está ligado ao ODS 11 da ONU: Cidades e comunidades sustentáveis. "
        "Esse objetivo busca cidades inclusivas, seguras, resilientes e sustentáveis.\n"
        "A meta 11.7 fala em acesso universal a espaços públicos seguros, inclusivos e acessíveis, "
        "em especial para pessoas idosas e pessoas com deficiência.\n"
        "Cada denúncia ajuda a mostrar onde as calçadas e travessias precisam de atenção."
    )


def resposta_oficial() -> str:
    return (
        "O AcessaCidade não é um serviço oficial do governo. Eu não consigo prometer conserto nem prazo.\n"
        "A equipe do AcessaCidade registra o andamento de cada denúncia pelos status. "
        "\"Resolvida\" é um registro da equipe, não uma confirmação da prefeitura.\n"
        "Para pedir o conserto de forma oficial, procure também o canal de atendimento da prefeitura da sua cidade."
    )


def resposta_rota() -> str:
    return (
        "Não consigo dizer se um caminho é acessível ou seguro. "
        "O AcessaCidade mostra só os problemas que as pessoas registraram. "
        "Se um lugar não tem denúncia, isso não quer dizer que ele é acessível.\n"
        "Você pode ver as denúncias de um bairro na tela \"Consultar\" (#/consultar). "
        "Se encontrar um problema no caminho, registre em \"Registrar\" (#/registrar)."
    )


def resposta_emergencia() -> str:
    return (
        "Se alguém se machucou ou corre perigo agora, ligue para o SAMU (192) ou para os Bombeiros (193).\n"
        "O AcessaCidade não atende emergências. Depois que todos estiverem seguros, "
        "você pode registrar o problema da calçada na tela \"Registrar\" (#/registrar)."
    )


def resposta_indicadores(ind: dict | None) -> str:
    if not ind or not isinstance(ind.get("total"), (int, float)):
        return (
            "Os números de denúncias estão na tela \"Painel\" (#/painel). "
            "Lá você vê totais por bairro, por tipo de problema, por status e pelo resultado da triagem."
        )
    linhas = [f"Segundo o painel do AcessaCidade, há {ind['total']} denúncias registradas."]
    rotulos = {
        "possiveis_buracos": "com possível buraco identificado na foto",
        "inconclusivas": "com análise inconclusiva",
        "nao_identificadas": "sem indício suficiente de buraco",
        "sem_imagem": "sem fotografia",
    }
    for campo, rot in rotulos.items():
        if isinstance(ind.get(campo), (int, float)):
            linhas.append(f"- {ind[campo]} {rot}")
    por_status = ind.get("por_status")
    if isinstance(por_status, list) and por_status:
        linhas.append(
            "Por status: " + "; ".join(f"{i['rotulo']}: {i['total']}" for i in por_status if i.get("rotulo"))
            + "."
        )
    if ind.get("inclui_simulados"):
        linhas.append("Atenção: esses números incluem denúncias de demonstração (dados simulados).")
    linhas.append("Veja os gráficos completos na tela \"Painel\" (#/painel).")
    return "\n".join(linhas)


def resposta_fora_escopo() -> str:
    return (
        "Desculpe, não consigo ajudar com esse assunto. "
        "Eu só respondo sobre o AcessaCidade: registrar problemas de acessibilidade, "
        "entender status e triagem da foto, escrever a descrição, consultar protocolo e privacidade.\n"
        "Posso ajudar com algum desses temas?"
    )


# ---------------------------------------------------------------------------
# Modo "descricao": estrutura o texto da pessoa sem inventar fatos
# ---------------------------------------------------------------------------
_TIPO_PALAVRAS: list[tuple[str, tuple[str, ...]]] = [
    ("PISO_TATIL", ("piso tatil", "piso podotatil")),
    ("RAMPA_IRREGULAR", ("rampa",)),
    ("OBSTACULO_TEMPORARIO", ("entulho", "cacamba", "carro", "veiculo", "moto", "obra", "tapume", "material de construcao")),
    ("OBSTACULO_FIXO", ("poste", "lixeira", "placa", "orelhao", "arvore", "banca", "hidrante", "grade")),
    ("BURACO", ("buraco", "cratera", "afundamento", "afundad")),
    ("CALCADA_DANIFICADA", ("quebrad", "desnivel", "rachad", "solta", "soltas", "levantad", "esburacad", "irregular")),
]
_VIA_PALAVRAS = ("no meio da rua", "no asfalto", "na via", "na pista", "na faixa", "travessia", "faixa de pedestre", "leito da rua")

_IMPACTO_PALAVRAS: list[tuple[str, tuple[str, ...]]] = [
    ("IMPEDE_PASSAGEM", ("nao consig", "nao consegu", "nao da para passar", "nao da pra passar", "impede", "bloque", "fechad", "impossivel passar", "nao passa")),
    ("RISCO_QUEDA", ("cai ", "caiu", "cair", "tropec", "queda", "perigo", "perigos", "risco", "acidente", "torc")),
    ("DIFICULTA_PASSAGEM", ("dificil", "dificulta", "dificuldade", "atrapalha", "desviar", "ir para a rua", "descer para a rua")),
]

_AFETADOS = [
    ("cadeirante", "cadeirantes"), ("cadeira de rodas", "pessoas em cadeira de rodas"),
    ("idos", "pessoas idosas"), ("cego", "pessoas com deficiência visual"),
    ("deficiencia visual", "pessoas com deficiência visual"), ("baixa visao", "pessoas com baixa visão"),
    ("bengala", "pessoas que usam bengala"), ("muleta", "pessoas que usam muletas"),
    ("andador", "pessoas que usam andador"), ("carrinho de bebe", "pessoas com carrinho de bebê"),
    ("mobilidade reduzida", "pessoas com mobilidade reduzida"), ("gestante", "gestantes"),
    ("crianc", "crianças"), ("pedestre", "pedestres"), ("deficiencia", "pessoas com deficiência"),
]

_LOGRADOURO_RE = re.compile(
    r"\b(?:rua|r\.|avenida|av\.?|travessa|alameda|praça|praca|estrada|largo|viela|rodovia)\s+[^,.;\n]{2,60}",
    re.IGNORECASE,
)
_REFERENCIA_RE = re.compile(
    r"\b(?:em frente (?:a|ao|à|da|do)|perto (?:de|da|do)|próximo (?:a|ao|à|da|do)|proximo (?:a|ao|da|do)|"
    r"ao lado (?:de|da|do)|na esquina (?:de|da|do|com)|esquina com|na frente (?:de|da|do)|atrás (?:de|da|do))\s+[^,.;\n]{2,60}",
    re.IGNORECASE,
)
_BAIRRO_RE = re.compile(r"\bbairro\s+[^,.;\n]{2,40}", re.IGNORECASE)
_MEDIDA_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:cm|centímetros?|centimetros?|m|metros?|mm|milímetros?|palmos?)\b"
    r"(?:\s*(?:de\s+)?(?:largura|comprimento|profundidade|fundura|altura|diâmetro|diametro))?",
    re.IGNORECASE,
)
_TAMANHO_PALAVRAS_RE = re.compile(
    r"\b(?:muito\s+)?(?:grande|enorme|pequen[oa]|fundo|funda|profund[oa]|largo|larga|comprid[oa])\b",
    re.IGNORECASE,
)


def _primeiro_trecho(regex: re.Pattern[str], texto: str) -> str | None:
    m = regex.search(texto)
    return m.group(0).strip() if m else None


def estruturar_descricao(texto_usuario: str) -> dict:
    """Extrai O quê / Onde / Tamanho / Impacto / Quem é afetado do texto (sem inventar)."""
    texto, pii = remover_dados_pessoais(texto_usuario)
    n = normalizar(texto) + " "

    tipo = None
    for chave, palavras in _TIPO_PALAVRAS:
        if any(p in n for p in palavras):
            tipo = chave
            break
    if tipo == "BURACO":
        tipo = "BURACO_VIA" if any(p in n for p in _VIA_PALAVRAS) else "BURACO_CALCADA"

    impacto = None
    for chave, palavras in _IMPACTO_PALAVRAS:
        if any(p in n for p in palavras):
            impacto = chave
            break

    afetados: list[str] = []
    for palavra, rotulo in _AFETADOS:
        if palavra in n and rotulo not in afetados:
            if rotulo == "pessoas com deficiência" and any("deficiência" in a for a in afetados):
                continue
            afetados.append(rotulo)

    onde_partes: list[str] = []
    for trecho in (
        _primeiro_trecho(_LOGRADOURO_RE, texto),
        _primeiro_trecho(_BAIRRO_RE, texto),
        _primeiro_trecho(_REFERENCIA_RE, texto),
    ):
        if trecho and not any(trecho.lower() in p.lower() for p in onde_partes):
            onde_partes.append(trecho)
    medidas = [m.group(0).strip() for m in _MEDIDA_RE.finditer(texto)]
    if not medidas:
        medidas = [m.group(0).strip() for m in _TAMANHO_PALAVRAS_RE.finditer(texto)]

    return {
        "texto": texto.strip(),
        "dados_pessoais_removidos": pii,
        "o_que": domain.TIPOS_OBSTACULO[tipo] if tipo else None,
        "tipo_obstaculo": tipo,
        "onde": "; ".join(dict.fromkeys(onde_partes)) or None,
        "tamanho": ", ".join(dict.fromkeys(medidas)) or None,
        "impacto": impacto,
        "impacto_rotulo": domain.IMPACTOS[impacto] if impacto else None,
        "afetados": afetados,
    }


def _sugestao_sem_dados_pessoais(texto: str) -> str:
    """Remove frases com marcadores de dado pessoal e ajusta maiúsculas/pontuação."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+|\n+", texto) if f.strip()]
    frases = [f for f in frases if "removido]" not in f]
    frases = [f[0].upper() + f[1:] for f in frases]
    sugestao = " ".join(frases)
    if sugestao and not sugestao.endswith((".", "!", "?")):
        sugestao += "."
    return sugestao[:1000]


def resposta_descricao(texto_usuario: str) -> tuple[str, list[str]]:
    avisos: list[str] = []
    info = estruturar_descricao(texto_usuario)
    texto = info["texto"]
    if info["dados_pessoais_removidos"]:
        avisos.append(
            "Tirei da sugestão algo que parece dado pessoal (telefone, e-mail ou CPF). Não coloque esses dados na descrição."
        )
    sinais = [info["o_que"], info["onde"], info["tamanho"], info["impacto"], info["afetados"]]
    if len(texto) < 10 or not any(sinais):
        return (
            "Posso ajudar a escrever a descrição. Conte com suas palavras:\n"
            "1. O que é o problema? (buraco, calçada quebrada, rampa, poste no caminho...)\n"
            "2. Onde fica? (rua, número, bairro e um ponto de referência)\n"
            "3. Qual o tamanho aproximado?\n"
            "4. Como isso atrapalha a passagem?\n"
            "5. Quem é mais afetado? (cadeirantes, pessoas idosas, pessoas cegas...)",
            avisos,
        )

    linhas = ["Organizei o que você contou. Não acrescentei nenhuma informação nova.", ""]
    linhas.append(f"- O quê: {info['o_que'] or '[não informado]'}")
    linhas.append(f"- Onde: {info['onde'] or '[não informado]'}")
    linhas.append(f"- Tamanho aproximado: {info['tamanho'] or '[não informado]'}")
    linhas.append(f"- Impacto: {info['impacto_rotulo'] or '[não informado]'}")
    linhas.append(f"- Quem é afetado: {', '.join(info['afetados']) if info['afetados'] else '[não informado]'}")

    sugestao = _sugestao_sem_dados_pessoais(texto)
    linhas += ["", "Sugestão de descrição (com as suas palavras):", sugestao, ""]
    if info["tipo_obstaculo"]:
        linhas.append(f"Tipo de obstáculo sugerido no formulário: {domain.TIPOS_OBSTACULO[info['tipo_obstaculo']]}")
    if info["impacto"]:
        linhas.append(f"Impacto sugerido no formulário: {domain.IMPACTOS[info['impacto']]}")

    perguntas = []
    if not info["o_que"]:
        perguntas.append("Qual é o problema? (buraco, calçada quebrada, rampa, obstáculo...)")
    if not info["onde"]:
        perguntas.append("Onde fica? Diga a rua, o bairro e um ponto de referência.")
    if not info["tamanho"]:
        perguntas.append("Qual o tamanho aproximado? (por exemplo, em centímetros ou palmos)")
    if not info["impacto"]:
        perguntas.append("O problema impede a passagem, dificulta ou causa risco de queda?")
    if not info["afetados"]:
        perguntas.append("Quem é mais afetado? (cadeirantes, pessoas idosas, pessoas cegas...)")
    if perguntas:
        linhas += ["", "Para deixar a descrição mais completa, responda:"]
        linhas += [f"- {p}" for p in perguntas]
    if len(sugestao) < 10:
        linhas.append("A descrição precisa ter pelo menos 10 caracteres.")
    return "\n".join(linhas).strip(), avisos


# ---------------------------------------------------------------------------
# Orquestração do modo alternativo
# ---------------------------------------------------------------------------
def responder(ctx: ContextoPreparado) -> RespostaRegras:
    avisos: list[str] = []
    d = ctx.denuncia
    prefixo = ""
    if ctx.protocolo_nao_encontrado:
        prefixo = resposta_protocolo_nao_encontrado(ctx.protocolo_solicitado or "")
    if d and d.get("simulado"):
        avisos.append(AVISO_SIMULADO)

    if not ctx.mensagem:
        return RespostaRegras(resposta_sobre(), "vazia", avisos)

    if ctx.modo == "descricao":
        texto, av = resposta_descricao(ctx.mensagem)
        return RespostaRegras(texto, "descricao", avisos + av)

    if ctx.modo == "explicar_resultado":
        avisos.append(AVISO_TRIAGEM)
        if d:
            return RespostaRegras(resposta_triagem_denuncia(d), "explicar_resultado", avisos)
        corpo = resposta_triagem_generica()
        return RespostaRegras(f"{prefixo}\n\n{corpo}" if prefixo else corpo, "explicar_resultado", avisos)

    intencao = detectar_intencao(ctx.mensagem)

    if intencao == "emergencia":
        return RespostaRegras(resposta_emergencia(), intencao, avisos)

    if prefixo and intencao in ("protocolo", "status", "triagem", "fora_escopo", "saudacao", "oficial"):
        return RespostaRegras(prefixo, "protocolo_nao_encontrado", avisos)

    if d and intencao in ("protocolo", "status", "fora_escopo", "saudacao", "oficial"):
        avisos.append(AVISO_NAO_OFICIAL)
        corpo = resposta_resumo_denuncia(d)
        if intencao == "oficial":
            corpo += "\n\n" + resposta_oficial()
        return RespostaRegras(corpo, "protocolo", avisos)
    if d and intencao == "triagem":
        avisos.append(AVISO_TRIAGEM)
        return RespostaRegras(resposta_triagem_denuncia(d), "explicar_resultado", avisos)

    corpo: str
    if intencao == "registrar":
        corpo = resposta_registrar()
    elif intencao == "status":
        corpo = resposta_status(ctx.mensagem)
        avisos.append(AVISO_NAO_OFICIAL)
    elif intencao == "triagem":
        corpo = resposta_triagem_generica()
        avisos.append(AVISO_TRIAGEM)
    elif intencao == "protocolo":
        corpo = resposta_protocolo_sem_numero()
    elif intencao == "descricao":
        texto, av = resposta_descricao(ctx.mensagem)
        corpo, avisos = texto, avisos + av
    elif intencao == "privacidade":
        corpo = resposta_privacidade()
    elif intencao == "ods":
        corpo = resposta_ods()
    elif intencao == "oficial":
        corpo = resposta_oficial()
    elif intencao == "rota":
        corpo = resposta_rota()
    elif intencao == "indicadores":
        corpo = resposta_indicadores(ctx.indicadores)
    elif intencao in ("sobre", "saudacao"):
        corpo = resposta_sobre()
    else:
        corpo = resposta_fora_escopo()

    if prefixo:
        corpo = f"{prefixo}\n\n{corpo}"
    return RespostaRegras(corpo, intencao, avisos)
