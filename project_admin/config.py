"""Monitoring PC 관리자 프로그램의 공통 설정값입니다."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

# SQLite 설정
DATABASE_PATH = BASE_DIR / "factory.db"

# 제품 STEP별 기준 이미지는 DB와 분리하여 이 폴더에 보관합니다.
STEP_GUIDE_IMAGE_DIR = BASE_DIR / "step_guide_images"
STEP_GUIDE_MAX_SOURCE_BYTES = 10 * 1024 * 1024
STEP_GUIDE_MAX_RESPONSE_BYTES = 3 * 1024 * 1024

# 로그인한 Jetson의 실제 IP는 Gateway가 동적으로 연결하며 수신 Port만 공통입니다.
JETSON_SERVER_PORT = 5000
JETSON_CONNECTION_TIMEOUT_SECONDS = 3.0

# WorkerPC 로그인과 상태 메시지를 받을 Monitoring PC Gateway
WORKER_GATEWAY_HOST = "0.0.0.0"
WORKER_GATEWAY_PORT = 5001
WORKER_GATEWAY_MAX_CLIENTS = 16

# 샘플 데이터는 sample_data.py를 수동 실행하여 생성합니다.
AUTO_CREATE_SAMPLE_DATA = False
