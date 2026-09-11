#!/usr/bin/env bash
# ==============================================================================
# 중앙 관제 프로그램 (Admin Monitoring PC) 실행 스크립트
# ==============================================================================
# [중요] 반드시 프로젝트 최상위 루트 디렉토리(AI_Standard_Process_System/)에서 실행해야 합니다.
# 가상환경(.venv) 및 의존성 패키지가 없으면 최초 1회 자동 설치 후 실행합니다.
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 하위 폴더 실행 차단 및 프로젝트 루트 실행 검증
if [ "$PWD" != "$PROJECT_ROOT" ]; then
    echo "❌ [오류] 본 프로그램은 반드시 프로젝트 루트 디렉토리에서 실행해야 합니다."
    echo "   현재 위치: $PWD"
    echo "   프로젝트 루트: $PROJECT_ROOT"
    echo ""
    echo "👉 아래 명령어로 프로젝트 루트로 이동하여 실행해 주십시오:"
    echo "   cd \"$PROJECT_ROOT\" && bash run_admin.sh"
    exit 1
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

    python3 -m venv --system-site-packages --prompt venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
    touch .venv/.installed
    echo "✅ 의존성 설치가 완료되었습니다!"
fi

# 가상환경 프롬프트 이름 통일 ('(.venv)' -> '(venv)')
if [ -f ".venv/bin/activate" ]; then
    sed -i "s/VIRTUAL_ENV_PROMPT='(.venv) '/VIRTUAL_ENV_PROMPT='(venv) '/g" ".venv/bin/activate" 2>/dev/null || true
fi

# 터미널 시작 시 가상환경 (venv) 자동 활성화 설정 (~/.bashrc)
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ] && ! grep -Fqs "$PROJECT_ROOT/.venv/bin/activate" "$HOME/.bashrc"; then
    echo "🔗 터미널 시작 시 가상환경 (venv) 자동 활성화를 ~/.bashrc에 등록합니다..."
    cat << EOF >> "$HOME/.bashrc"

# AI Standard Process System - 가상환경 자동 활성화
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi
EOF
fi

exec "$PROJECT_ROOT/.venv/bin/python3" "$PROJECT_ROOT/project_admin/main.py" "$@"
