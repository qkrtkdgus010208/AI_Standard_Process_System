# STM32F411 공정 제어 펌웨어

STM32F411RE 마이크로컨트롤러 기반의 조립 공정 현장 제어기 펌웨어입니다. 물리 버튼 입력(Check, Pause/Resume, Reset), 1~9번 STEP LED 및 FAIL LED 점등, 상태별 부저 음향 재생, Jetson Orin Nano와의 UART 통신을 제어합니다.

## 1. 파일 구조

```text
project_stm/
├── main.c              # 메인 루프, UART 명령 수신 처리, 버튼 상태 전이 처리
├── key.c / key.h       # 물리 버튼 EXTI 인터럽트 및 디바운스 제어
├── led.c / led.h       # STEP 1~9 LED 및 FAIL LED 점등/소등 제어
├── buzzer.c / buzzer.h # 상태별 6종 부저 멜로디 시퀀스 및 비동기 재생 제어
├── timer.c / timer.h   # TIM2 기반 부저 타이머 (비동기 사운드 생성)
├── uart.c / uart.h     # USART2 (115200 bps) 송수신 및 인터럽트 핸들러
├── clock.c             # 시스템 클럭 설정
├── systick.c           # SysTick 딜레이
├── device_driver.h     # 하드웨어 드라이버 통합 헤더
├── macro.h             # 비트 조작 매크로
├── Makefile            # arm-none-eabi-gcc 빌드 및 st-flash 플래싱 스크립트
└── rom_0x08000000.lds  # 링커 스크립트
```

## 2. 하드웨어 핀맵 (Pinout)

### 2.1 버튼 입력 (EXTI 인터럽트, Active Low)
- **BTN 0 (Check 버튼)**: `PB0` (누르면 Qt로 `"Check\n"` 송신 → AI 비전 판정 실행)
- **BTN 1 (Pause/Resume 버튼)**: `PB1` (토글 방식, 누르면 `"Pause\n"` 또는 `"Resume\n"` 송신)
- **BTN 2 (Reset 버튼)**: `PB2` (누르면 `"Reset\n"` 송신 → 불량 등록 및 초기화)

### 2.2 LED 출력
- **STEP 1 ~ STEP 9 LED**: `PC0` ~ `PC8` (각 단계 진행 시 해당 LED 점등, Active High)
- **FAIL LED**: `PC9` (AI 판정 FAIL 시 빨간색 경보 LED 점등)

### 2.3 부저 출력
- **Buzzer**: `PB13` (TIM2 기반 소프트웨어 주파수/타이밍 토글 제어)

### 2.4 통신 (USART2)
- **TX**: `PA2`
- **RX**: `PA3`
- Baudrate: `115200 bps`

## 3. 부저 사운드 명세 (상태별 6종 사운드)

현장 작업자가 화면을 보지 않고도 청각적으로 현재 상태를 인지할 수 있도록 6종의 고유 멜로디를 제공합니다:

| 상태 | 매크로 상수 | 멜로디 구성 | 설명 |
|:---|:---|:---|:---|
| **PASS** | `SOUND_PASS` | 2음 (상승음: 도-솔) | 단계 정상 완료 및 다음 단계 진입 |
| **FAIL** | `SOUND_FAIL` | 3음 (저음 경보: 낮은음 반복) | AI 판정 불량 경보 |
| **공정 완료** | `SOUND_COMPLETE` | 5음 (승리 팡파레) | 제품의 모든 STEP 조립 완료 |
| **수동 불량** | `SOUND_DEFECT` | 2음 (하강음: 솔-도) | 작업자 수동 불량 등록 및 리셋 |
| **일시정지** | `SOUND_PAUSE` | 2음 (미-도 단음) | 작업 일시정지 알림 |
| **작업재개** | `SOUND_RESUME` | 2음 (도-미 단음) | 작업 재개 알림 |

## 4. UART 통신 프로토콜

### 4.1 수신 명령 (Jetson Qt → STM32, 단일 문자)
- `'S'`: 작업 시작 (STEP 1 LED ON, 버튼 활성화)
- `'P'`: PASS (다음 STEP LED ON, PASS 부저)
- `'F'`: FAIL (FAIL LED ON, FAIL 부저)
- `'C'`: 전체 공정 완료 (LED 전체 소등, 완료 팡파레 부저, 대기 상태 복귀)
- `'R'`: 불량 등록/리셋 (LED 전체 소등, 불량 부저, 0단계 대기 상태 초기화)
- `'U'`: Qt GUI 일시정지 (STEP LED OFF, 일시정지 부저)
- `'M'`: Qt GUI 작업 재개 (STEP LED ON, 작업재개 부저)
- `'E'`: 프로그램 종료/로그아웃 (전 LED 소등, 부저 정지, 버튼 인터럽트 비활성화)
- `'1'` ~ `'9'`: 서버 작업 복원 (해당 STEP n의 LED ON 및 버튼 활성화)

### 4.2 송신 명령 (STM32 → Jetson Qt, 문자열)
- `"Check\n"`: 버튼 0 누름 시 송신
- `"Pause\n"`: 버튼 1 누름 시 (진행 중일 때) 송신
- `"Resume\n"`: 버튼 1 누름 시 (일시정지 중일 때) 송신
- `"Reset\n"`: 버튼 2 누름 시 송신

## 5. 빌드 및 플래싱

### 툴체인 요구사항
- `arm-none-eabi-gcc`
- `stlink` (`st-flash`)

### 컴파일
```bash
make clean
make
```

### 보드 플래싱 (ST-LINK 연결 상태)
```bash
make run
```
성공 시 `Flash written and verified! jolly good!` 메시지가 출력됩니다.
