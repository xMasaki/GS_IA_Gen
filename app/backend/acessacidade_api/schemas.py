"""Modelos Pydantic v2 de entrada e saída (contrato, seção 4)."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

StatusChave = Literal["RECEBIDA", "EM_ANALISE", "AGUARDANDO_REVISAO", "ENCAMINHADA", "RESOLVIDA"]
RevisaoChave = Literal["CONFIRMADO", "DESCARTADO"]


# ----------------------------------------------------------------- saída
class Visao(BaseModel):
    classificacao: str
    rotulo: str
    pontuacao: float
    explicacao: list[str]
    metricas: dict[str, Any]
    deteccoes: list[dict[str, Any]]
    imagens: dict[str, str]
    versao_algoritmo: str
    aviso: str


class ItemHistorico(BaseModel):
    status: str
    status_rotulo: str
    alterado_em: str
    observacao: Optional[str] = None


class Denuncia(BaseModel):
    """Objeto público de denúncia. Nunca contém o nome do denunciante."""

    id: int
    protocolo: str
    criado_em: str
    atualizado_em: str
    logradouro: str
    numero: Optional[str] = None
    bairro: str
    cidade: str
    ponto_referencia: Optional[str] = None
    tipo_obstaculo: str
    tipo_obstaculo_rotulo: str
    descricao: str
    impacto: str
    impacto_rotulo: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: str
    status_rotulo: str
    origem: str
    simulado: bool
    possui_imagem: bool
    visao: Optional[Visao] = None
    revisao_humana: Optional[str] = None


class DenunciaDetalhe(Denuncia):
    historico: list[ItemHistorico] = Field(default_factory=list)


class DenunciaCriada(DenunciaDetalhe):
    mensagem: str


class ListaDenuncias(BaseModel):
    itens: list[Denuncia]
    total: int
    pagina: int
    limite: int


class AnaliseVisao(BaseModel):
    classificacao: str
    rotulo: str
    pontuacao: float
    explicacao: list[str]
    metricas: dict[str, Any]
    deteccoes: list[dict[str, Any]]
    imagens: dict[str, str]
    versao_algoritmo: str
    aviso: str


class ContagemChave(BaseModel):
    chave: str
    rotulo: str
    total: int


class ContagemDia(BaseModel):
    data: str
    total: int


class Indicadores(BaseModel):
    total: int
    possiveis_buracos: int
    inconclusivas: int
    nao_identificadas: int
    sem_imagem: int
    por_categoria: list[ContagemChave]
    por_bairro: list[ContagemChave]
    por_status: list[ContagemChave]
    por_resultado_visao: list[ContagemChave]
    por_origem: list[ContagemChave]
    por_dia: list[ContagemDia]
    recentes: list[Denuncia]
    inclui_simulados: bool
    gerado_em: str


class ComponentesHealth(BaseModel):
    banco: str
    visao: str
    assistente: str


class Health(BaseModel):
    status: str
    versao: str
    ambiente: str
    componentes: ComponentesHealth


class AssistenteResposta(BaseModel):
    resposta: str
    fonte: Literal["llm", "fallback"]
    modelo: Optional[str] = None
    denuncia_referenciada: Optional[str] = None
    avisos: list[str] = Field(default_factory=list)


class Mensagem(BaseModel):
    detail: str


# ----------------------------------------------------------------- entrada
class AlteracaoStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StatusChave
    observacao: Optional[str] = Field(default=None, max_length=500)
    revisao_humana: Optional[RevisaoChave] = None

    @field_validator("observacao")
    @classmethod
    def _limpar(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class MensagemHistorico(BaseModel):
    papel: Literal["usuario", "assistente"]
    texto: str = Field(max_length=1000)


class AssistenteEntrada(BaseModel):
    mensagem: str = Field(min_length=1, max_length=1000)
    modo: Literal["geral", "descricao", "explicar_resultado"] = "geral"
    protocolo: Optional[str] = Field(default=None, max_length=40)
    contexto_tela: Optional[str] = Field(default=None, max_length=60)
    historico: list[MensagemHistorico] = Field(default_factory=list, max_length=50)

    @field_validator("mensagem")
    @classmethod
    def _mensagem_nao_vazia(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("A mensagem não pode ficar em branco.")
        return v.strip()

    @field_validator("protocolo")
    @classmethod
    def _protocolo(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().upper()
        return v or None
