#!/usr/bin/env bash
# ==============================================================================
# 중앙 관제 프로그램 (Admin Monitoring PC) 실행 스크립트
# ==============================================================================
# [중요] 반드시 프로젝트 최상위 루트 디렉토리(AI_Standard_Process_System/)에서 실행해야 합니다.
# 가상환경(.venv) 및 의존성 패키지가 없으면 최초 1회 자동 설치 후 실행합니다.
# ==============================================================================

(return 0 2>/dev/null) && SOURCED=1 || SOURCED=0

if [ "$SOURCED" -eq 0 ]; then
    set -e
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 하위 폴더 실행 차단 및 프로젝트 루트 실행 검증
if [ "$PWD" != "$PROJECT_ROOT" ]; then
    echo "❌ [오류] 본 프로그램은 반드시 프로젝트 루트 디렉토리에서 실행해야 합니다."
    echo "   현재 위치: $PWD"
    echo "   프로젝트 루트: $PROJECT_ROOT"
    echo ""
    echo "👉 아래 명령어로 프로젝트 루트로 이동하여 실행해 주십시오:"
    echo "   cd \"$PROJECT_ROOT\" && bash run_admin.sh"
    if [ "$SOURCED" -eq 1 ]; then return 1; else exit 1; fi
fi

# 가상환경 및 패키지 자동 세팅 (최초 1회 또는 설치 미완료 시)
if [ ! -f ".venv/.installed" ]; then
    echo "⚙️ 필수 환경을 설정합니다 (시스템 패키지, 가상환경 및 의존성 패키지)..."
    sudo apt update && sudo apt install -y v4l-utils python3-pyqt5 python3-venv

    # 이전 실행 실패 등으로 불완전한 가상환경이 남아있다면 초기화
    if [ -d ".venv" ] && [ ! -f ".venv/.installed" ]; then
        echo "⚠️ 미완료된 기존 가상환경(.venv)을 정리하고 새로 구성합니다..."
        rm -rf .venv
    fi

    echo "📦 가상환경(.venv)을 생성합니다..."
    python3 -m venv --system-site-packages --prompt venv .venv

    # 가상환경 프롬프트 이름 통일 ('(.venv)' -> '(venv)')
    if [ -f ".venv/bin/activate" ]; then
        sed -i "s/VIRTUAL_ENV_PROMPT='(.venv) '/VIRTUAL_ENV_PROMPT='(venv) '/g" ".venv/bin/activate" 2>/dev/null || true
    fi

    # [핵심] 시작부터 (venv) 활성화 후 설치 진행!
    echo "⚡ 가상환경 (venv)을 활성화합니다..."
    source .venv/bin/activate

    echo "📥 활성화된 (venv) 가상환경에 패키지를 설치합니다..."
    pip install --upgrade pip
    pip install -r requirements.txt
    touch .venv/.installed
    echo "✅ 의존성 설치가 완료되었습니다!"
else
    # 이미 설치된 경우에도 시작부터 (venv) 활성화
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi
fi

# 새 터미널 창에서도 가상환경 (venv)이 자동 활성화되도록 ~/.bashrc에 등록
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ] && ! grep -Fqs "$PROJECT_ROOT/.venv/bin/activate" "$HOME/.bashrc"; then
    echo "🔗 새 터미널 창에서도 (venv)가 자동 활성화되도록 ~/.bashrc에 등록합니다..."
    cat << EOF >> "$HOME/.bashrc"

# AI Standard Process System - 가상환경 자동 활성화
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi
EOF
fi

# 프로그램 실행 및 (venv) 유지
echo "🚀 중앙 관제 프로그램을 실행합니다... (가상환경: ${VIRTUAL_ENV:-미활성화})"
python "$PROJECT_ROOT/project_admin/main.py" "$@"

if [ "$SOURCED" -eq 1 ]; then
    # source로 실행한 경우: 이미 현재 터미널에 (venv)가 활성화되어 있으므로 그대로 유지
    return 0
else
    # bash로 실행한 경우: 현재 터미널 창을 (venv)가 활성화된 최신 쉘로 즉시 교체하여 유지
    echo ""
    echo "🔄 (venv) 가상환경 상태를 계속 유지합니다..."
    exec bash
fi
