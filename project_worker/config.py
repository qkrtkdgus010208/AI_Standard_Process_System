"""Jetson 작업자 프로그램의 변경 가능한 설정값입니다."""

from pathlib import Path


# Jetson 장비 연결 전에는 True로 유지합니다.
TEST_MODE = False

# UART / STM32 설정 (Jetson/Linux 장치 경로)
UART_ENABLED = not TEST_MODE
UART_PORT = "/dev/ttyUSB0"  # 필요 시 "/dev/ttyACM0"으로 변경
UART_BAUDRATE = 115200
UART_TIMEOUT_SECONDS = 0.2

# Monitoring PC가 접속할 작업자 PC TCP 서버 설정
TCP_ENABLED = True
TCP_SERVER_HOST = "0.0.0.0"
TCP_SERVER_PORT = 5000
TCP_CLIENT_TIMEOUT_SECONDS = 1.0

# 작업자 인증과 상태 전송을 받을 Monitoring PC 주소
MONITORING_PC_IP = "10.10.15.5"
MONITORING_AUTH_PORT = 5001
MONITORING_REQUEST_TIMEOUT_SECONDS = 3.0

# Camera 설정: "mock", "usb", "csi" 중 선택
CAMERA_BACKEND = "usb"
USB_CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30

# Jetson CSI Camera용 기본 nvarguscamerasrc Pipeline
CSI_GSTREAMER_PIPELINE = (
    "nvarguscamerasrc ! "
    "video/x-raw(memory:NVMM), width=(int)1280, height=(int)720, "
    "format=(string)NV12, framerate=(fraction)30/1 ! "
    "nvvidconv flip-method=0 ! video/x-raw, format=(string)BGRx ! "
    "videoconvert ! video/x-raw, format=(string)BGR ! appsink drop=1"
)

# AI 설정: 현재는 mock, 이후 pytorch/tensorrt 구현체로 교체 가능
AI_BACKEND = "mock"
AI_MODEL_PATH = Path(__file__).resolve().parent / "models" / "model.engine"
AI_INFERENCE_INTERVAL_MS = 800

# TEST_MODE용 기본 제품 목록
DEFAULT_PRODUCTS = [
    {"product_id": "P001", "product_name": "스마트 액추에이터 A", "total_steps": 5},
    {"product_id": "P002", "product_name": "모터 드라이버 B", "total_steps": 4},
    {"product_id": "P003", "product_name": "센서 컨트롤러 C", "total_steps": 3},
]

# TEST_MODE 초기 작업 정보
DEFAULT_EMPLOYEE_ID = "1001"
DEFAULT_EMPLOYEE_NAME = "홍길동"
DEFAULT_PRODUCT_ID = "P001"
DEFAULT_PRODUCT_NAME = "스마트 액추에이터 A"
DEFAULT_TOTAL_STEPS = 5
