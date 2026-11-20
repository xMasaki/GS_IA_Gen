<#
.SYNOPSIS
    Executa o AcessaCidade localmente (sem Docker) no Windows PowerShell.

.DESCRIPTION
    1. Vai para a raiz do repositório.
    2. (Opcional, -Instalar) cria o venv .venv e instala requirements.txt.
    3. Carrega o arquivo .env, se existir (sem sobrescrever variáveis já definidas na sessão).
    4. Define o PYTHONPATH do contrato de integração (seção 2.1).
    5. Sobe o uvicorn com acessacidade_api.main:app (porta APP_PORT, padrão 8000).

.EXAMPLE
    .\scripts\run_local.ps1
    .\scripts\run_local.ps1 -Instalar
    .\scripts\run_local.ps1 -Porta 8001 -Recarregar
    .\scripts\run_local.ps1 -Endereco 0.0.0.0    # expõe na rede local (use com cuidado)

.NOTES
    Se a execução de scripts estiver bloqueada:
      powershell -ExecutionPolicy Bypass -File .\scripts\run_local.ps1
#>
[CmdletBinding()]
param(
    [string]$Endereco = "127.0.0.1",
    [int]$Porta = 0,
    [switch]$Instalar,
    [switch]$Recarregar
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz

$VenvPython = Join-Path $Raiz ".venv\Scripts\python.exe"

if ($Instalar -and -not (Test-Path $VenvPython)) {
    Write-Host "Criando ambiente virtual .venv ..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.11 -m venv .venv
    } else {
        & python -m venv .venv
    }
}
if (-not (Test-Path $VenvPython)) {
    Write-Error "Ambiente virtual não encontrado em .venv. Rode: .\scripts\run_local.ps1 -Instalar"
}
if ($Instalar) {
    & $VenvPython -m pip install -r requirements.txt
}

# Carrega .env (KEY=VALUE; ignora comentários e linhas vazias; não sobrescreve a sessão)
$ArquivoEnv = Join-Path $Raiz ".env"
if (Test-Path $ArquivoEnv) {
    foreach ($linha in Get-Content -Path $ArquivoEnv -Encoding UTF8) {
        $t = $linha.Trim()
        if ($t -eq "" -or $t.StartsWith("#") -or -not $t.Contains("=")) { continue }
        $idx = $t.IndexOf("=")
        $nome = $t.Substring(0, $idx).Trim()
        $valor = $t.Substring($idx + 1).Trim().Trim('"').Trim("'")
        if (-not [Environment]::GetEnvironmentVariable($nome, "Process")) {
            [Environment]::SetEnvironmentVariable($nome, $valor, "Process")
        }
    }
    Write-Host "Variáveis carregadas de .env (valores não exibidos)."
} else {
    Write-Host "Arquivo .env não encontrado: usando padrões (tokens vazios = rotas protegidas desativadas)."
}

if ($Porta -le 0) {
    $Porta = if ($env:APP_PORT) { [int]$env:APP_PORT } else { 8000 }
}
if (-not $env:DATA_DIR) { $env:DATA_DIR = "./data/runtime" }

$sep = [IO.Path]::PathSeparator
$env:PYTHONPATH = @(
    (Join-Path $Raiz "app\backend"),
    (Join-Path $Raiz "01-Generative-AI-Engineering\src"),
    (Join-Path $Raiz "04-Applied-Computer-Vision\src")
) -join $sep

$argsUvicorn = @("-m", "uvicorn", "acessacidade_api.main:app", "--app-dir", "app/backend",
                 "--host", $Endereco, "--port", "$Porta")
if ($Recarregar) { $argsUvicorn += "--reload" }

Write-Host "AcessaCidade em http://$($Endereco):$Porta  (documentação da API: /docs; Ctrl+C para parar)"
& $VenvPython @argsUvicorn
