#!/usr/bin/env bash
# =====================================================================
# AcessaCidade — execução local SEM Docker (Linux, macOS ou Git Bash no Windows)
#
#   ./scripts/run_local.sh                 # sobe em http://127.0.0.1:8000
#   ./scripts/run_local.sh --instalar      # cria .venv e instala requirements.txt
#   PORTA=8001 ./scripts/run_local.sh
#   ENDERECO=0.0.0.0 ./scripts/run_local.sh   # expõe na rede local (use com cuidado)
#
# Passos: raiz do repo -> venv -> carrega .env (se existir, sem sobrescrever
# variáveis já exportadas) -> PYTHONPATH do contrato (seção 2.1) -> uvicorn.
# =====================================================================
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

# venv: Linux/macOS usa .venv/bin; Git Bash no Windows usa .venv/Scripts
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
else
  PY=""
fi

if [ "${1:-}" = "--instalar" ]; then
  if [ -z "$PY" ]; then
    echo "Criando ambiente virtual .venv ..."
    if command -v python3.11 >/dev/null 2>&1; then python3.11 -m venv .venv; else python3 -m venv .venv || python -m venv .venv; fi
    if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; else PY=".venv/Scripts/python.exe"; fi
  fi
  "$PY" -m pip install -r requirements.txt
fi

if [ -z "$PY" ]; then
  echo "Ambiente virtual .venv não encontrado. Rode: ./scripts/run_local.sh --instalar" >&2
  exit 1
fi

# Carrega .env sem executar o arquivo como script (evita interpretação de comandos)
if [ -f .env ]; then
  while IFS= read -r linha || [ -n "$linha" ]; do
    linha="${linha%$'\r'}"
    case "$linha" in ''|'#'*) continue ;; esac
    case "$linha" in *=*) ;; *) continue ;; esac
    nome="${linha%%=*}"; nome="$(echo "$nome" | tr -d '[:space:]')"
    valor="${linha#*=}"; valor="${valor#\"}"; valor="${valor%\"}"; valor="${valor#\'}"; valor="${valor%\'}"
    if [[ "$nome" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && [ -z "${!nome:-}" ]; then
      export "$nome=$valor"
    fi
  done < .env
  echo "Variáveis carregadas de .env (valores não exibidos)."
else
  echo "Arquivo .env não encontrado: usando padrões (tokens vazios = rotas protegidas desativadas)."
fi

PORTA="${PORTA:-${APP_PORT:-8000}}"
ENDERECO="${ENDERECO:-127.0.0.1}"
export DATA_DIR="${DATA_DIR:-./data/runtime}"

# Separador do PYTHONPATH: ';' para o Python do Windows (Git Bash), ':' nos demais
case "$(uname -s 2>/dev/null || echo desconhecido)" in
  MINGW*|MSYS*|CYGWIN*) SEP=";" ; BASE="$(cd "$RAIZ" && pwd -W 2>/dev/null || echo "$RAIZ")" ;;
  *) SEP=":" ; BASE="$RAIZ" ;;
esac
export PYTHONPATH="${BASE}/app/backend${SEP}${BASE}/01-Generative-AI-Engineering/src${SEP}${BASE}/04-Applied-Computer-Vision/src"

echo "AcessaCidade em http://${ENDERECO}:${PORTA}  (documentação da API: /docs; Ctrl+C para parar)"
exec "$PY" -m uvicorn acessacidade_api.main:app --app-dir app/backend --host "$ENDERECO" --port "$PORTA"
