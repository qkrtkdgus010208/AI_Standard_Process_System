# Jetson Orin Nano 작업자 프로그램

현장 작업자를 위한 **AI 비전 검사 및 표준 공정 추적 단말 프로그램** (PyQt5)입니다.

중앙 관제 PC(Monitoring PC)와 TCP Socket으로 실시간 통신하여 인증, 제품 목록 및 STEP 기준 이미지를 동기화하고, 현장 STM32 제어기와 UART 시리얼로 연동되어 4종 물리 버튼 입력, 1~9번 STEP LED, FAIL LED 및 7종 부저 음향을 제어합니다.

---

## 1. 파일 및 모듈 구조

OOP 원칙(단일 책임 원칙, Facade/Controller 패턴, 비동기 스레드 분리)에 따라 모듈화되어 있습니다.

```text
project_worker/
├── main.py                     # 프로그램 진입점 및 세션 기반 화면(로그인 ↔ 작업창) 전환
├── config.py                   # 장치 포트, 백엔드, v4l2 카메라 설정, AI 엔진 등 전역 설정
├── ai/                         # TensorRT 기반 AI 모델 추론 및 조립 정합성 검사 모듈
│   ├── detector.py             # TensorRT / YOLO 모델 추론 래퍼 (Detector)
│   ├── normalizer.py           # 기준 부품(reference) 대비 상대 좌표 정규화 모듈
│   ├── inspector.py            # 목표 부품 존재 여부 및 위치 오차 정합성 판정기
│   ├── pass_fail_test.py       # 카메라/모델 정합성 및 PASS/FAIL 오프라인 테스트 도구
│   ├── racing_car.json         # 레이싱카 조립 공정 정의 및 정합성 레시피
│   ├── pickup_truck.json       # 픽업트럭 조립 공정 정의 및 정합성 레시피
│   ├── bug_fighter.json        # 버그파이터 조립 공정 정의 및 정합성 레시피
│   ├── yollo26n_fp32.engine    # TensorRT FP32 가속 추론 엔진 파일
│   └── yollo26n.onnx           # YOLO 객체 검출 ONNX 모델 파일
├── devices/                    # 하드웨어 디바이스 제어 및 비동기 스레드
│   ├── ai_judge.py             # AI 비전 추론 비동기 스레드 (AiInferenceThread, TensorRtJudge, MockJudge)
│   ├── camera_manager.py       # USB/CSI/Mock 카메라 프레임 캡처 및 v4l2-ctl 제어 (CameraThread)
│   ├── stm_controller.py       # STM32 UART 명령 전송 및 로그 캡슐화 컨트롤러 (StmController)
│   └── uart_manager.py         # STM32 시리얼 통신 포트 탐색 및 수신 스레드 (UartReceiverThread)
├── services/                   # 비즈니스 로직 및 상태 머신 서비스
│   ├── auth_manager.py         # 작업자 인증 세션 관리 (WorkerSession, AuthResult, AuthRequestThread)
│   ├── product_service.py      # 제품 목록 및 STEP 기준 가이드 이미지 비동기 조회 서비스
│   ├── state_reporter.py       # 큐 기반 비동기 작업 상태 이벤트 서버 전송 (MonitoringEventThread)
│   └── work_state.py           # 공정 STEP/상태 머신 컨트롤러 (WorkStateController, WorkSnapshot)
├── network/                    # 저수준 TCP 네트워크 통신
│   ├── network_client.py       # TCP JSON 통신 및 연결 헬스체크 (send_json_request, ServerCheckThread)
│   ├── protocol.py             # TCP/UART 메시지 파싱 및 Base64 디코딩 (parse_message, decode_message_text)
│   ├── server_monitor.py       # 관제 PC 서버 연결 상태 주기적 감시 모듈 (ServerMonitor)
│   └── tcp_server.py           # Monitoring PC 관리자 호출 수신 TCP 서버 (:5000, TcpServerThread)
├── ui/                         # 작업자 UI 컴포넌트 레이어
│   ├── worker_window.py        # 작업자 메인 GUI (카메라/기준 이미지, 상태 표시, 제어 버튼, 시스템 로그)
│   ├── login_window.py         # 작업자 로그인 UI
│   ├── theme.py                # 시스템 공통 다크 모던 테마 QSS
│   └── dialogs/
│       └── ai_result_dialog.py # AI 품질 판정 결과 상세 다이얼로그 (바운딩박스 및 상대좌표 시각화)
└── tests/                      # 자동화 단위 테스트
    └── test_state_reporter.py
```

---

## 2. 주요 기능 및 AI 비전 파이프라인

- **공정 라이프사이클 관리**:
  `대기(idle)` → `작업 진행(running)` → `일시정지(paused)` → `작업 완료(complete)` / `불량 등록(defect)`.
- **TensorRT 가속 AI 비전 검사 파이프라인**:
  1. 작업자가 STM32의 Check 버튼(PB3)을 누르면 현재 카메라 프레임 캡처.
  2. `yollo26n_fp32.engine`을 통해 객체 검출(Bounding Box, Class ID, Confidence).
  3. 기준 부품(`reference`, 예: `car_base`) 중심 좌표를 기준으로 목표 부품들의 상대 좌표 정규화(`normalizer.py`).
  4. 제품별 레시피 JSON과 비교하여 목표 부품 누락 여부 및 허용 오차(`tolerance_x`, `tolerance_y`) 내 정합성 검사(`inspector.py`).
  5. 검사 결과(PASS/FAIL)에 따라 다음 STEP 자동 전이, STM32 LED/부저 동기화 및 관제 서버로 트랜잭션 보고.
- **v4l2-ctl 하드웨어 카메라 제어**:
  Linux `v4l-utils`를 통해 웹캠(Logitech C270 등)의 수동 노출(Manual Exposure), 대비, 선명도를 하드웨어 레벨에서 직접 제어하며 데이터셋과 동일한 상하좌우 반전(`flipCode=-1`) 지원.
- **STEP 기준 이미지 비교**:
  관리자가 등록한 정상 조립 가이드 이미지를 관제 서버로부터 비동기 수신하여 카메라 실시간 영상 바로 옆에 나란히 표시.
- **이전 작업 자동 복원 (Work State Persistence)**:
  로그인 시 관제 서버에 기록된 미완료 작업(제품번호, 진행 STEP, 일시정지 상태)을 자동 조회하여 작업 상태와 STM32 하드웨어 LED/부저를 즉시 동기화.
- **서버 단절 감시**:
  관제 서버와의 TCP 연결 상태를 주기적으로 감시하여 서버 비정상 다운 시 경고 알림 후 안전 모드로 전환.

---

## 3. UART 프로토콜 (Qt ↔ STM32)

- 통신 설정: Baudrate `115200 bps`, Data `8-N-1`
- 포트 자동 탐색: `/dev/ttyACM0`, `/dev/ttyACM1`, `/dev/ttyUSB0`, `/dev/ttyUSB1` 순차 자동 감지 및 권한 확인.

### 3.1 STM32 → Qt(Jetson) (하드웨어 버튼 입력, 문자열 + `\n`)

| 메시지 | 하드웨어 버튼 (핀) | 공정 상태 동작 |
|:---|:---:|:---|
| `Start\n` | BTN_START (`PB2`) | 대기 상태(0단계)일 때 공정 시작 (`on_start_work_clicked`) |
| `Check\n` | BTN_CHECK (`PB3`) | 현재 카메라 프레임으로 AI 비전 검사 실행 (`request_ai_judgement`) |
| `Pause\n` | BTN_PAUSE (`PB4`) | 공정 진행 중일 때 일시정지 (`work_controller.pause()`) |
| `Resume\n` | BTN_PAUSE (`PB4`) | 일시정지 상태일 때 공정 재개 (`work_controller.resume()`) |
| `Reset\n` | BTN_RESET (`PB5`) | 공정 진행 중일 때 수동 불량 등록 및 초기화 (`work_controller.register_defect()`) |

### 3.2 Qt(Jetson) → STM32 (하드웨어 제어 명령, 단일 문자)

| 명령 | 기능 | STM32 동작 |
|:---:|:---|:---|
| `'S'` | 작업 시작 | STEP 1 LED 점등, `SOUND_START` 부저 재생, 버튼 인터럽트 활성화 |
| `'P'` | 단계 PASS | 현재 STEP LED 소등, 다음 STEP LED 점등, `SOUND_PASS` 부저 재생 |
| `'F'` | 단계 FAIL | FAIL LED 점등, `SOUND_FAIL` 경보 부저음 재생 |
| `'C'` | 공정 전체 완료 | 모든 STEP 완료 시 전 LED 소등, `SOUND_COMPLETE` 팡파레 부저 재생, 대기 상태 복귀 |
| `'R'` | 불량 등록 / 리셋 | 수동 불량 등록 시 전 LED 소등, `SOUND_DEFECT` 부저 재생, 0단계 대기 초기화 |
| `'U'` | GUI 일시정지 | 현재 STEP LED 소등, Check 버튼 비활성화, `SOUND_PAUSE` 부저 재생 |
| `'M'` | GUI 작업 재개 | 현재 STEP LED 점등, Check 버튼 활성화, `SOUND_RESUME` 부저 재생 |
| `'E'` | 프로그램 종료 / 대기 | 로그아웃 또는 앱 종료 시 모든 LED 소등, 부저 정지, 버튼 비활성화 (대기 모드) |
| `'1'` ~ `'9'` | 서버 작업 복원 | 서버에서 복원된 STEP n의 LED를 점등하고 버튼 인터럽트 활성화 |

---

## 4. Jetson Orin Nano 설치 및 실행

> [!IMPORTANT]
> **모든 프로그램 실행은 반드시 프로젝트 최상위 루트 디렉토리(`AI_Standard_Process_System/`)에서 수행해야 합니다.**  
> 하위 폴더(`project_worker/`)로 이동하여 실행하지 마십시오.

UART 시리얼 udev 영구 권한, v4l-utils 도구, 가상환경(`.venv`), 의존성 패키지가 없으면 최초 1회 자동 설정 후 즉시 실행됩니다:

```bash
# 프로젝트 최상위 루트 디렉토리(AI_Standard_Process_System/)에서 실행
bash run_worker.sh
```

### 수동 가상환경 패키지 설치 시 (참고)
```bash
sudo apt install -y v4l-utils python3-pyqt5 python3-venv
pip install -r requirements_worker.txt
```

---

## 5. AI 비전 검사 오프라인 테스트 도구 (`pass_fail_test.py`)

GUI 없이 터미널에서 카메라 영상 취득, v4l2-ctl 노출 설정, YOLO TensorRT 모델 추론, JSON 레시피 정합성 판정을 단독으로 검증할 수 있는 스크립트입니다:

```bash
# 프로젝트 최상위 루트 디렉토리에서 실행
python3 project_worker/ai/pass_fail_test.py racing_car.json
```
- 인자로 `racing_car.json`, `pickup_truck.json`, `bug_fighter.json` 중 선택 가능합니다.

---

## 6. 개발 환경 테스트 모드 (TEST_MODE)

Jetson 보드나 STM32 하드웨어 장비 없이 일반 PC에서 UI 및 네트워크 연동을 테스트할 수 있습니다.  
`project_worker/config.py`에서 `TEST_MODE = True`로 설정하면 가상 웹캠(Mock)과 Mock AI, 테스트 계정이 활성화됩니다.

- **테스트 로그인 계정**: 직원번호 `1001`, 비밀번호 `worker1234`

---

## 7. 자동화 단위 테스트 실행

작업 상태 이벤트 전송 큐 및 스레드 로직을 검증하는 단위 테스트입니다. **반드시 프로젝트 최상위 루트 디렉토리에서 실행**합니다:

```bash
PYTHONPATH=project_worker python3 -m unittest discover -s project_worker/tests -p "test*.py"
```
