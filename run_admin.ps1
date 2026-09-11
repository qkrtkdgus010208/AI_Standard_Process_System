# ==============================================================================
# 중앙 관제 프로그램 (Admin Monitoring PC) Windows PowerShell 실행 스크립트
# ==============================================================================
# [중요] 프로젝트 최상위 루트 디렉토리(AI_Standard_Process_System\)에서 실행됩니다.
# 가상환경(.venv) 및 의존성 패키지가 없으면 최초 1회 자동 설치 후 즉시 실행합니다.
# ==============================================================================

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $ProjectRoot

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host " AI Standard Process System - Monitoring PC (관리자 프로그램)" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan

# [1단계] Python 감지
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3"
}

if (-not $pythonCmd) {
    Write-Host "`n❌ [오류] Python이 설치되어 있지 않거나 PATH 환경 변수에 등록되어 있지 않습니다." -ForegroundColor Red
    Write-Host "   Python 3.10 이상을 설치하고 'Add python.exe to PATH'에 체크해 주세요."
    Write-Host "   공식 다운로드: https://www.python.org/downloads/`n"
    pause
    exit 1
}

# [2단계] 가상환경(.venv) 및 패키지 설정
if ((Test-Path ".venv") -and -not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "⚠️ Linux 등 타 OS에서 생성되었거나 손상된 .venv가 감지되어 새로 구성합니다..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force ".venv"
}

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "`n⚙️ Windows 가상환경(.venv)을 새로 생성합니다..." -ForegroundColor Yellow
    if ($pythonCmd -eq "python") {
        python -m venv --prompt venv .venv
    } else {
        py -3 -m venv --prompt venv .venv
    }
}

if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "❌ 가상환경 생성에 실패했습니다. Python 버전을 확인해 주세요." -ForegroundColor Red
    pause
    exit 1
}

Write-Host "⚡ 가상환경 (venv)을 활성화합니다..."
& ".venv\Scripts\Activate.ps1"

Write-Host "📥 의존성 패키지를 확인 및 동기화합니다 (이미 설치된 항목은 자동 스킵)..."
pip install -r requirements_admin.txt

# [3단계] 프로그램 실행
Write-Host "`n🚀 중앙 관제 프로그램을 실행합니다..." -ForegroundColor Green
try {
    python project_admin\main.py @args
} catch {
    Write-Host "`n❌ 프로그램 실행 중 오류가 발생했습니다: $_" -ForegroundColor Red
    pause
    exit 1
}
