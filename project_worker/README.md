# Jetson Orin Nano 작업자 프로그램

관리자용 Monitoring PC와 분리된 작업자용 PyQt5 프로그램입니다. Ubuntu Linux와 ARM64 환경을 기준으로 하며 Windows 경로나 COM Port를 사용하지 않습니다.

## 파일 구조

```text
WorkerPC/
├── main.py                # 프로그램 시작
├── worker_window.py       # 작업자 UI와 Signal 연결
├── work_state.py          # STEP/Pause/Reset/PASS/FAIL 상태 제어
├── camera_manager.py      # USB/CSI/Mock Camera Thread
├── ai_judge.py            # Mock/향후 PyTorch/TensorRT AI 분리
├── uart_manager.py        # STM32 UART 수신 Thread
├── tcp_server.py          # Monitoring PC TCP 수신 Thread
├── protocol.py            # TCP/UART 메시지 파싱
├── config.py              # 장치 Port 및 Backend 설정
├── theme.py               # 관리자 프로그램과 통일된 UI 테마
├── requirements.txt       # Jetson용 Python 추가 패키지
└── requirements-dev.txt   # 일반 개발 PC TEST_MODE용
```

## Jetson Orin Nano 설치

Jetson의 OpenCV는 GStreamer 지원이 포함된 Ubuntu/JetPack 패키지를 사용하는 편이 안전합니다.

```bash
sudo apt update
sudo apt install -y python3-pip python3-pyqt5 python3-opencv python3-serial python3-numpy
```

pyserial을 pip로 설치할 경우 다음 명령을 사용할 수 있습니다.

```bash
python3 -m pip install -r requirements.txt
```

## 실행

```bash
cd WorkerPC
python3 main.py
```

처음에는 `config.py`의 `TEST_MODE = True` 상태로 실행합니다. 실제 Camera나 STM32가 없어도 로그인, Mock Camera, Mock AI, PASS/FAIL, Pause, Reset, TCP 호출 수신을 시험할 수 있습니다.

TEST_MODE 작업자 계정은 다음과 같습니다.

```text
직원번호: 1001
비밀번호: worker1234
```

로그인 후 직원번호와 이름은 인증 Session에서 고정되며 작업자가 변경할 수 없습니다. 작업상태 전송에도 입력값이 아닌 Session Token을 사용합니다.

## UART / STM32 설정

`config.py`에서 다음 값을 실제 장치에 맞게 수정합니다.

```python
UART_PORT = "/dev/ttyUSB0"  # 또는 /dev/ttyACM0
UART_BAUDRATE = 115200
```

Linux에서는 현재 사용자가 Serial Port에 접근하지 못할 수 있습니다. 사용자를 `dialout` 그룹에 추가한 뒤 로그아웃/로그인하거나 재부팅합니다.

```bash
sudo usermod -aG dialout $USER
```

현재 Port의 그룹과 권한을 확인할 수 있습니다.

```bash
ls -l /dev/ttyUSB0
groups
```

임시 확인 목적으로만 다음과 같이 권한을 변경할 수도 있지만, 재연결하면 초기화될 수 있으므로 `dialout` 그룹 사용을 권장합니다.

```bash
sudo chmod 666 /dev/ttyUSB0
```

실제 UART를 사용할 때는 `config.py`를 다음처럼 변경합니다.

```python
TEST_MODE = False
UART_ENABLED = True
```

지원하는 기본 STM32 수신 명령은 `PASS`, `FAIL`, `PAUSE`, `RESUME`, `RESET`, `START`입니다. 메시지는 줄바꿈으로 끝나야 합니다.

## USB Camera

`config.py`에서 다음 값을 설정합니다.

```python
CAMERA_BACKEND = "usb"
USB_CAMERA_INDEX = 0
```

내부적으로 `cv2.VideoCapture(0)`에 해당하는 OpenCV Backend를 사용합니다.

## Jetson CSI Camera

```python
CAMERA_BACKEND = "csi"
```

CSI Camera는 `config.py`의 `CSI_GSTREAMER_PIPELINE`을 사용합니다. Sensor 해상도, 회전, FPS에 맞게 Pipeline을 수정할 수 있습니다. Pipeline 처리는 `camera_manager.py`에만 있으므로 UI 코드는 변경할 필요가 없습니다.

Jetson에서 GStreamer 지원 여부는 다음처럼 확인할 수 있습니다.

```bash
python3 -c "import cv2; print(cv2.getBuildInformation())"
```

출력에서 `GStreamer: YES`인지 확인합니다.

## AI Backend 교체

현재 `config.py`는 다음과 같이 Mock AI를 사용합니다.

```python
AI_BACKEND = "mock"
```

PyTorch 또는 TensorRT를 연결할 때는 `ai_judge.py`에서 `BaseJudge.predict()` 인터페이스를 구현하고 `create_judge()`에 Backend를 추가합니다. UI는 `JudgeResult`만 받으므로 PyTorch, CUDA, TensorRT를 직접 import하지 않습니다. 추론은 `AiInferenceThread`에서 실행되어 PyQt Main Thread를 막지 않습니다.

## Monitoring PC TCP 연결

작업자 프로그램은 기본적으로 모든 Network Interface의 Port 5000에서 대기합니다.

```python
TCP_SERVER_HOST = "0.0.0.0"
TCP_SERVER_PORT = 5000
```

Monitoring PC의 `tcp_client.py`에는 Jetson의 실제 IP를 설정합니다.

```python
JETSON_SERVER_IP = "192.168.0.50"
JETSON_SERVER_PORT = 5000
```

호출 메시지는 다음 형식입니다.

```text
CALL|1001
```

실제 모드의 작업자 로그인과 상태 전송을 위해서는 관리자 프로그램도 실행되어 있어야 합니다. `config.py`의 Monitoring PC 주소를 실제 IP로 변경합니다.

```python
MONITORING_PC_IP = "192.168.0.10"
MONITORING_AUTH_PORT = 5001
```

Monitoring PC는 Port 5001에서 작업자 계정을 `factory.db`로 검증하고 Session Token을 발급합니다. 이후 상태 메시지에 직원번호를 받지 않고 Token 소유자의 직원번호를 서버에서 결정하므로 로그인한 작업자는 다른 직원의 데이터로 전송할 수 없습니다.

Jetson의 IP는 다음 명령으로 확인할 수 있습니다.

```bash
hostname -I
```

Ubuntu Firewall을 사용하는 경우 Port 허용이 필요할 수 있습니다.

```bash
sudo ufw allow 5000/tcp
sudo ufw allow 5001/tcp
```

## Thread 구조

- PyQt Main Thread: 화면 갱신과 Button 처리만 담당
- `CameraThread`: USB/CSI Camera Frame 읽기
- `AiInferenceThread`: Mock 또는 실제 AI 추론
- `UartReceiverThread`: STM32 UART 메시지 수신
- `TcpServerThread`: Monitoring PC TCP 연결 및 호출 메시지 수신

모든 장치 연결 실패는 상태 표시와 시스템 기록에 남고, 프로그램 전체를 즉시 종료하지 않습니다.
