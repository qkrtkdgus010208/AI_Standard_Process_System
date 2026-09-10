#!/usr/bin/env bash
# ==============================================================================
# 작업자 단말 프로그램 (Worker GUI) 실행 스크립트
# ==============================================================================
# [중요] 반드시 프로젝트 최상위 루트 디렉토리(AI_Standard_Process_System/)에서 실행해야 합니다.
# UART 시리얼 권한(udev) 및 가상환경(.venv)이 없으면 최초 1회 자동 설정 후 실행합니다.
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
    echo "   cd \"$PROJECT_ROOT\" && bash run_worker.sh"
    exit 1
fi

# 1. UART 시리얼 포트 udev 권한 영구 등록 (최초 1회 실행 시)
if [ ! -f "/etc/udev/rules.d/99-stm32-serial.rules" ]; then
    echo "🔧 UART 시리얼 포트(STM32) 영구 접근 권한(udev)을 자동 설정합니다..."
    RULE_FILE="/etc/udev/rules.d/99-stm32-serial.rules"
    sudo bash -c "cat << 'EOF' > ${RULE_FILE}
KERNEL==\"ttyACM[0-9]*\", MODE=\"0666\"
KERNEL==\"ttyUSB[0-9]*\", MODE=\"0666\"
KERNEL==\"ttyTHS[0-9]*\", MODE=\"0666\"
EOF"
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    sudo usermod -aG dialout "$USER"
fi

# 현재 연결된 포트 즉시 0666 권한 부여 (쓰기 권한 없을 시 적용)
for dev in /dev/ttyACM* /dev/ttyUSB* /dev/ttyTHS*; do
    if [ -e "$dev" ] && [ ! -w "$dev" ]; then
        sudo chmod 666 "$dev" 2>/dev/null || true
    fi
done

# 2. 가상환경 및 패키지 자동 세팅 (최초 1회 실행 시)
if [ ! -f ".venv/bin/python3" ]; then
    echo "⚙️ 최초 실행을 감지했습니다. 가상환경(.venv) 및 의존성 패키지를 설치합니다..."
    sudo apt update && sudo apt install -y v4l-utils
    python3 -m venv --system-site-packages .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
    echo "✅ 의존성 설치가 완료되었습니다!"
fi

exec "$PROJECT_ROOT/.venv/bin/python3" "$PROJECT_ROOT/project_worker/main.py" "$@"
