# Jetson Orin Nano 작업자 프로그램

관리자용 Monitoring PC와 연동되고 STM32 하드웨어와 UART로 통신하는 작업자용 PyQt5 프로그램입니다. Ubuntu Linux와 ARM64 환경을 기준으로 하며 Windows 경로나 COM Port를 사용하지 않습니다.

## 1. 파일 및 모듈 구조

OOP 원칙(단일 책임 원칙, Facade/Controller 패턴)에 따라 명확히 모듈화되어 있습니다.

```text
project_worker/
├── main.py                # 프로그램 진입점 및 세션 기반 화면(로그인 ↔ 작업창) 전환
├── config.py              # 장치 Port, Backend, 네트워크 등 전역 설정
├── ai/                    # YOLO 모델 검출, 정규화 및 조립 정합성 검사
│   ├── detector.py        # YOLOv8 모델 추론 래퍼
│   ├── normalizer.py      # 기준 부품 대비 상대 좌표 계산
│   └── inspector.py       # 부품 존재 여부 및 위치 오차 판정
├── ui/                    # 작업자 UI 컴포넌트 레이어
│   ├── worker_window.py   # 작업자 메인 GUI (카메라·STEP 기준 이미지, 상태 표시, 제어 버튼, 로그)
│   ├── login_window.py    # 작업자 로그인 UI
│   ├── theme.py           # 관리자 프로그램과 통일된 모던 UI 테마
│   └── dialogs/
│       └── ai_result_dialog.py # AI 품질 판정 결과 상세 다이얼로그 (바운딩박스 시각화)
├── services/              # 비즈니스 로직 및 상태 관리 서비스
│   ├── auth_manager.py    # 작업자 인증 세션 관리 (WorkerSession, AuthResult, AuthRequestThread)
│   ├── product_service.py # 제품 목록과 현재 STEP 기준 이미지 비동기 조회 서비스
│   ├── state_reporter.py  # 큐 기반 비동기 작업상태 이벤트 서버 전송 (MonitoringEventThread)
│   └── work_state.py      # 공정 STEP/상태 머신 컨트롤러 (WorkStateController, WorkSnapshot)
├── devices/               # 하드웨어 디바이스 제어 및 AI 추론
│   ├── ai_judge.py        # AI 추론 비동기 스레드 (AiInferenceThread, BaseJudge, MockJudge)
│   ├── camera_manager.py  # USB/CSI/Mock 카메라 프레임 캡처 스레드 (CameraThread)
│   ├── stm_controller.py  # STM32 UART 명령 전송 캡슐화 컨트롤러 (StmController)
│   └── uart_manager.py    # STM32 시리얼 통신 수신 스레드 (UartReceiverThread)
├── network/               # 저수준 TCP 네트워크 통신
│   ├── network_client.py  # TCP JSON 통신 및 연결 헬스체크 (send_json_request, ServerCheckThread)
│   ├── protocol.py        # TCP/UART 메시지 파싱 및 Base64 디코딩 (parse_message, decode_message_text)
│   ├── server_monitor.py  # 관제 PC 서버 연결 주기적 감시 모듈 (ServerMonitor)
│   └── tcp_server.py      # Monitoring PC 관리자 호출 수신 TCP 서버 (TcpServerThread)
└── tests/                 # 자동화 단위 테스트
    └── test_state_reporter.py
```

## 2. 주요 기능 및 아키텍처

- **공정 라이프사이클 관리**: 대기(idle) → 작업 진행(running) → 일시정지(paused) → 작업 완료(complete) / 불량 등록(defect).
- **AI 비전 검사 연동**: 카메라 영상을 받아 실시간 추론(`AiInferenceThread`), PASS 시 다음 STEP 자동 진입, FAIL 시 불량 알람 및 재검사 대기.
- **STEP 기준 이미지 비교**: 관리자가 등록한 정상 예시 이미지를 현재 카메라 옆에 표시하고 STEP 전환 시 자동 갱신.
- **이전 작업 자동 복원**: 로그인 시 서버에 남아있는 미완료 작업(제품번호, 진행 STEP, 일시정지 상태)을 자동 복원하고 STM32 LED/상태를 즉시 동기화.
- **서버 연결 감시**: 관제 서버와의 TCP 연결이 비정상 종료되면 경고 팝업 후 안전하게 프로그램 종료.
- **STM32 하드웨어 연동**: 물리 버튼(Check, Pause/Resume, Reset) 및 1~9번 STEP LED, FAIL LED, 상태별 부저 음향 제어.

## 3. UART 프로토콜 (Qt ↔ STM32)

Baudrate: `115200`, Data: `8-N-1`

### 3.1 Qt(Jetson) → STM32 (단일 문자 명령)

| 명령 | 기능 | 설명 |
|:---:|:---|:---|
| `'S'` | 작업 시작 | STEP 1 LED 점등, 버튼 인터럽트 활성화 |
| `'P'` | PASS | 현재 STEP LED 소등 후 다음 STEP LED 점등, PASS 부저 |
| `'F'` | FAIL | FAIL LED 점등, FAIL 경보 부저 |
| `'C'` | 공정 완료 | 모든 STEP 완료 시 전 LED 소등, 완료 팡파레 부저, 대기 상태 복귀 |
| `'R'` | 불량 등록 / 리셋 | 수동 불량 등록 시 LED 소등, 불량 부저, 0단계 대기 상태 초기화 |
| `'U'` | GUI 일시정지 | STEP LED 소등, Check 버튼 비활성화, 일시정지 부저 |
| `'M'` | GUI 작업 재개 | STEP LED 점등, Check 버튼 활성화, 작업재개 부저 |
| `'E'` | 프로그램 종료 / 대기 | 로그아웃 또는 앱 종료 시 모든 LED 소등, 부저 정지, 버튼 비활성화 |
| `'1'` ~ `'9'` | 서버 작업 복원 | 서버에서 복구된 STEP n의 LED를 점등하고 버튼 활성화 |

### 3.2 STM32 → Qt(Jetson) (문자열 + `\n`)

| 메시지 | 트리거 | 동작 |
|:---|:---|:---|
| `Check\n` | STM32 버튼 0 (PC0) 누름 | 현재 카메라 프레임으로 AI 검사 실행 |
| `Pause\n` | STM32 버튼 1 (PB1) 누름 (작업 중일 때) | 공정 일시정지 (GUI 버튼 및 상태 반영) |
| `Resume\n` | STM32 버튼 1 (PB1) 누름 (일시정지 중일 때) | 공정 작업 재개 |
| `Reset\n` | STM32 버튼 2 (PB2) 누름 | 공정 수동 불량 등록 및 초기화 |

## 4. Jetson Orin Nano 설치 및 실행

> [!IMPORTANT]
> **모든 프로그램 실행은 반드시 프로젝트 최상위 루트 디렉토리(`AI_Standard_Process_System/`)에서 수행해야 합니다.**  
> 하위 폴더(`project_worker/`)로 이동하여 실행하지 마십시오.

UART 시리얼 udev 권한, 가상환경, 의존성 패키지가 없으면 최초 1회 자동 설정 후 즉시 실행됩니다:

```bash
# 프로젝트 최상위 루트 디렉토리(AI_Standard_Process_System/)에서 실행
bash run_worker.sh
```

## 5. 개발 환경 테스트 모드 (TEST_MODE)

Jetson/STM32 장비 없이 일반 PC에서 UI 및 네트워크 연동을 테스트할 수 있습니다.
`project_worker/config.py`에서 `TEST_MODE = True`로 설정하면 가상 카메라와 Mock AI, 테스트 계정이 활성화됩니다.

- **테스트 로그인 계정**: 직원번호 `1001`, 비밀번호 `worker1234`

## 6. 자동화 단위 테스트 실행

작업 상태 이벤트 전송 큐 로직 등을 검증하는 단위 테스트입니다. **반드시 프로젝트 최상위 루트 디렉토리에서 실행**합니다:
```bash
PYTHONPATH=project_worker python3 -m unittest discover -s project_worker/tests -p "test*.py"
```
