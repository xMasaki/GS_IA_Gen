# syntax=docker/dockerfile:1
# =============================================================================
# AcessaCidade — imagem da aplicação (backend FastAPI + SPA + visão + helper IA)
#
# Build (na RAIZ do repositório — o contexto de build é a raiz):
#   docker build -f 06-Secure-DevOps-Cloud/docker/Dockerfile -t acessacidade:local .
#
# Decisões de segurança (Disciplina 06 — Deploy Blindado):
#   - Multi-stage: compiladores/pip ficam só no estágio "builder"; o estágio final
#     recebe apenas o venv pronto e o código necessário em tempo de execução.
#   - Base python:3.11-slim-bookworm: avaliada com Trivy (ver
#     06-Secure-DevOps-Cloud/docs/evidencias/validacoes_locais.md); tag fixa.
#   - pip, setuptools e wheel são REMOVIDOS da imagem final (do venv e do Python
#     do sistema): reduzem superfície de ataque e eliminam CVEs desses pacotes.
#   - Usuário não root com UID/GID fixos (10001). Código pertence ao root e é
#     somente leitura para a aplicação; só DATA_DIR é gravável.
#   - Nenhum segredo na imagem: tokens e chaves chegam apenas como variáveis de
#     ambiente em tempo de execução (.env local, GitHub Secrets ou ACI
#     secure_environment_variables).
#   - Nenhuma lib de sistema extra: o wheel do opencv-python-headless traz suas
#     dependências; as externas (glibc, libstdc++6, libgcc-s1, zlib1g) já
#     existem na base (verificado no ELF do wheel e no inventário da imagem).
# =============================================================================

ARG PYTHON_IMAGE=python:3.11-slim-bookworm

# -----------------------------------------------------------------------------
# Estágio 1 — builder: cria o venv e instala as dependências de runtime
# -----------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY requirements.txt /build/requirements.txt

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /build/requirements.txt \
    && /opt/venv/bin/pip uninstall -y setuptools wheel pip

# -----------------------------------------------------------------------------
# Estágio 2 — runtime: somente o necessário para executar
# -----------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime

ARG APP_VERSION=1.0.0
ARG VCS_REF=desconhecido
ARG SOURCE_URL=""

LABEL org.opencontainers.image.title="AcessaCidade" \
      org.opencontainers.image.description="Plataforma para registrar, triar por visão computacional e acompanhar denúncias de problemas de acessibilidade em calçadas (FIAP GS 2026.2 — ODS 11)" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="${SOURCE_URL}" \
      org.opencontainers.image.licenses="NOASSERTION" \
      org.opencontainers.image.vendor="Equipe AcessaCidade (FIAP)"

# Variáveis NÃO sensíveis. Segredos (ADMIN_TOKEN, PIPELINE_TOKEN,
# OPENROUTER_API_KEY) nunca são definidos aqui.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/app/app/backend:/app/01-Generative-AI-Engineering/src:/app/04-Applied-Computer-Vision/src" \
    APP_ENV=production \
    APP_PORT=8000 \
    DATA_DIR=/app/data/runtime \
    FRONTEND_DIR=/app/app/frontend

# Remove ferramentas de empacotamento do Python do sistema e cria o usuário
# de serviço sem shell de login e sem diretório home.
RUN python -m pip uninstall -y setuptools wheel pip \
    && groupadd --system --gid 10001 acessacidade \
    && useradd --system --uid 10001 --gid 10001 --no-create-home \
       --home-dir /nonexistent --shell /usr/sbin/nologin acessacidade

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

# Código da aplicação (pertence ao root -> somente leitura para o usuário 10001)
COPY app/backend /app/app/backend
COPY app/frontend /app/app/frontend
COPY 01-Generative-AI-Engineering/src /app/01-Generative-AI-Engineering/src
COPY 01-Generative-AI-Engineering/prompts /app/01-Generative-AI-Engineering/prompts
COPY 04-Applied-Computer-Vision/src /app/04-Applied-Computer-Vision/src
# Fotos SINTÉTICAS usadas pelo seed de demonstração
COPY data/samples/fotos /app/data/samples/fotos

# Único diretório gravável: banco SQLite + uploads (montar volume aqui)
RUN mkdir -p /app/data/runtime \
    && chown -R 10001:10001 /app/data/runtime \
    && chmod 0750 /app/data/runtime

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('APP_PORT', '8000'), timeout=4)"]

CMD ["uvicorn", "acessacidade_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
