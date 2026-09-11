#!/usr/bin/env bash
# ==============================================================================
# 작업자 단말 프로그램 (Worker GUI) 실행 스크립트
# ==============================================================================
# [중요] 반드시 프로젝트 최상위 루트 디렉토리(AI_Standard_Process_System/)에서 실행해야 합니다.
# UART 시리얼 권한(udev) 및 가상환경(.venv)이 없으면 최초 1회 자동 설정 후 실행합니다.
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
    echo "   cd \"$PROJECT_ROOT\" && bash run_worker.sh"
    if [ "$SOURCED" -eq 1 ]; then return 1; else exit 1; fi
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

# 2. 카메라 하드웨어 제어 유틸리티(v4l-utils) 자동 설치 확인
if ! command -v v4l2-ctl >/dev/null 2>&1; then
    echo "📷 카메라 하드웨어 제어 유틸리티(v4l-utils / v4l2-ctl)를 설치합니다..."
    sudo apt update && sudo apt install -y v4l-utils
fi

# 3. 가상환경(.venv) 생성 (미존재 시)
if [ ! -d ".venv" ] || [ ! -f ".venv/bin/activate" ]; then
    echo "⚙️ 가상환경(.venv)을 새로 생성합니다..."
    sudo apt update && sudo apt install -y python3-pyqt5 python3-venv
    rm -rf .venv
    python3 -m venv --system-site-packages --prompt venv .venv
    if [ -f ".venv/bin/activate" ]; then
        sed -i "s/VIRTUAL_ENV_PROMPT='(.venv) '/VIRTUAL_ENV_PROMPT='(venv) '/g" ".venv/bin/activate" 2>/dev/null || true
    fi
fi

# 4. 가상환경 활성화 및 패키지 검사/설치 (이미 설치된 패키지는 자동으로 건너뜀)
echo "⚡ 가상환경 (venv)을 활성화합니다..."
source .venv/bin/activate

echo "📥 의존성 패키지를 확인 및 동기화합니다 (이미 설치된 항목은 자동 스킵)..."
pip install -r requirements_worker.txt

# Jetson Orin 전용 PyTorch(CUDA 가속) 상태 확인 및 필요 시 자동 복원
if ! python3 -c "import torch; assert torch.cuda.is_available()" >/dev/null 2>&1; then
    if [ -f "/home/aidl/work/torch_whl/torch-2.3.0-cp310-cp310-linux_aarch64.whl" ]; then
        echo "🔧 Jetson Orin CUDA 가속 지원 PyTorch를 복원합니다..."
        pip install --force-reinstall --no-deps /home/aidl/work/torch_whl/torch-2.3.0-cp310-cp310-linux_aarch64.whl /home/aidl/work/torch_whl/torchvision-0.18.0a0+6043bc2-cp310-cp310-linux_aarch64.whl >/dev/null 2>&1 || true
    fi
fi

# 5. 새 터미널 창에서도 가상환경 (venv)이 자동 활성화되도록 ~/.bashrc에 등록
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ] && ! grep -Fqs "$PROJECT_ROOT/.venv/bin/activate" "$HOME/.bashrc"; then
    echo "🔗 새 터미널 창에서도 (venv)가 자동 활성화되도록 ~/.bashrc에 등록합니다..."
    cat << EOF >> "$HOME/.bashrc"

# AI Standard Process System - 가상환경 자동 활성화
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi
EOF
fi

# 6. 프로그램 실행 및 (venv) 유지
echo "🚀 작업자 프로그램을 실행합니다... (가상환경: ${VIRTUAL_ENV:-미활성화})"
python "$PROJECT_ROOT/project_worker/main.py" "$@"

if [ "$SOURCED" -eq 1 ]; then
    # source로 실행한 경우: 이미 현재 터미널에 (venv)가 활성화되어 있으므로 그대로 유지
    return 0
else
    # bash로 실행한 경우: 현재 터미널 창을 (venv)가 활성화된 최신 쉘로 즉시 교체하여 유지
    echo ""
    echo "🔄 (venv) 가상환경 상태를 계속 유지합니다..."
    exec bash
fi
