"""Jetson 작업자 프로그램의 변경 가능한 설정값입니다."""

# Jetson 장비 연결 전에는 True로 유지합니다.
TEST_MODE = False

# UART / STM32 설정 (Jetson/Linux 장치 경로)
UART_ENABLED = (
    True  # TEST_MODE와 독립적으로 제어. False면 UART 스레드가 대기 루프로만 실행됩니다.
)
UART_PORT = "/dev/ttyACM0"  # STM32 연결 포트 (/dev/ttyACM0 또는 /dev/ttyUSB0)
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
MONITORING_MAX_RESPONSE_BYTES = 5 * 1024 * 1024

# Camera 설정: "mock", "usb", "csi" 중 선택
CAMERA_BACKEND = "usb"
USB_CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30

# pass_fail_test.py / C270 웹캠 파라미터 설정 (v4l2-ctl 연동)
# Linux V4L2(100us 단위)에서 156 = 15.6ms ≈ 1/64초
CAMERA_V4L2_DEVICE = "/dev/video0"
CAMERA_AUTO_EXPOSURE = 1  # 1: 수동 노출(Manual), 3: 자동 노출(Auto)
CAMERA_EXPOSURE = 220  # 적정 셔터 노출값 (156 = 15.6ms ≈ 1/64초)
CAMERA_CONTRAST = 22
CAMERA_SHARPNESS = 255
CAMERA_FLIP = (
    True  # pass_fail_test.py 데이터셋 촬영 방향과 동일한 상하좌우 반전 (flipCode=-1)
)

# Jetson CSI Camera용 기본 nvarguscamerasrc Pipeline
CSI_GSTREAMER_PIPELINE = (
    "nvarguscamerasrc ! "
    "video/x-raw(memory:NVMM), width=(int)1280, height=(int)720, "
    "format=(string)NV12, framerate=(fraction)30/1 ! "
    "nvvidconv flip-method=0 ! video/x-raw, format=(string)BGRx ! "
    "videoconvert ! video/x-raw, format=(string)BGR ! appsink drop=1"
)

# AI 설정: tensorrt (실제 yolo26n_v2_fp16.engine 및 racing_car.json/pickup_truck.json 기반 검사)
AI_BACKEND = "tensorrt"

# 기본 제품 목록 (서버 미연동 시 또는 fallback용)
DEFAULT_PRODUCTS = [
    {"product_id": "P001", "product_name": "레이싱카", "total_steps": 6},
    {"product_id": "P002", "product_name": "픽업트럭", "total_steps": 6},
]
