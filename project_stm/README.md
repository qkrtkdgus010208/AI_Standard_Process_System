# STM32F411 공정 제어 펌웨어

STM32F411RE 마이크로컨트롤러 기반의 조립 공정 현장 제어기 펌웨어입니다. 물리 버튼 입력(Check, Pause/Resume, Reset), 1~9번 STEP LED 및 FAIL LED 점등, 상태별 부저 음향 재생, Jetson Orin Nano와의 UART 통신을 제어합니다.

---

## 1. 파일 구조

```text
project_stm/
├── Makefile            # arm-none-eabi-gcc 빌드 및 st-flash 플래싱 스크립트
├── rom_0x08000000.lds  # 링커 스크립트
├── include/            # 하드웨어 드라이버 및 CMSIS 헤더 파일
│   ├── buzzer.h        # 상태별 6종 부저 멜로디 시퀀스 정의
│   ├── device_driver.h # 하드웨어 드라이버 통합 헤더
│   ├── key.h           # 물리 버튼 인터럽트 및 디바운스 헤더
│   ├── led.h           # STEP 1~9 및 FAIL LED 제어 헤더
│   ├── macro.h         # 비트 조작 매크로
│   ├── timer.h         # TIM2 타이머 제어 헤더
│   ├── uart.h          # USART2 통신 헤더
│   └── *.h             # CMSIS 및 STM32F411 레지스터 헤더
└── src/                # C 소스 및 시작 어셈블리 코드
    ├── main.c          # Top-Down 메인 루프, 프로세스별 핸들러 모듈
    ├── buzzer.c        # 부저 음향 시퀀스 및 비동기 사운드 재생
    ├── clock.c         # 시스템 클럭 설정
    ├── crt0.s          # 시작 벡터 및 런타임 초기화 어셈블리
    ├── exception.c     # 시스템 예외 핸들러
    ├── key.c           # 물리 버튼 EXTI 인터럽트 제어
    ├── led.c           # STEP 1~9 및 FAIL LED 제어
    ├── runtime.c       # C 런타임 라이브러리 지원
    ├── system_stm32f4xx.c # CMSIS 시스템 초기화
    ├── systick.c       # SysTick 딜레이
    ├── timer.c         # TIM2 하드웨어 타이머 제어
    └── uart.c          # USART2 통신 및 인터럽트
```

---

## 2. 소프트웨어 아키텍처 (`main.c` 구조)

메인 파일은 유지보수와 코드 분석이 용이하도록 **Top-Down 구조**로 설계되어 있으며, `while (1)` 메인 루프 내부는 3개의 명확한 프로세스 메서드만 순차 실행됩니다.

```c
void Main(void)
{
    Sys_Init(115200);

    while (1)
    {
        Process_Uart_Command();  /* [1] UART 수신 명령 해석 및 상태 처리 */
        Process_Buzzer_Timer();   /* [2] TIM2 부저 재생 시퀀스 타이머 처리 */
        Process_Button_Event();   /* [3] 물리 버튼 인터럽트 이벤트 처리 */
    }
}
```

### 2.1 프로세스별 세부 모듈 및 핸들러

1. **`[1] Process_Uart_Command`**:
   - UART 수신 플래그(`Uart_Data_In`) 감지 시 수신 명령에 따른 전용 핸들러 실행:
     - `'S'`: `Handle_Uart_Start()` — 공정 시작 (STEP 1 LED ON, 버튼 활성화)
     - `'P'`: `Handle_Uart_Pass()` — PASS (다음 STEP LED ON, PASS 부저)
     - `'F'`: `Handle_Uart_Fail()` — FAIL (FAIL LED ON, 경보 부저)
     - `'C'`: `Handle_Uart_Complete()` — 전체 완료 (전 LED 소등, 팡파레 부저, 대기 상태 복귀)
     - `'R'`: `Handle_Uart_Defect()` — 불량 등록 (전 LED 소등, 불량 부저, 0단계 대기 초기화)
     - `'U'`: `Handle_Uart_Pause()` — GUI 일시정지 (STEP LED OFF, 일시정지 부저)
     - `'M'`: `Handle_Uart_Resume()` — GUI 작업재개 (STEP LED ON, 작업재개 부저)
     - `'E'`: `Handle_Uart_Exit()` — 프로그램 종료/로그아웃 (전 LED 소등, 부저 정지, 버튼 비활성화)
     - `'1'`~`'9'`: `Handle_Uart_Restore(step)` — 서버 이전 작업 복원 (해당 STEP 점등 및 버튼 활성화)

2. **`[2] Process_Buzzer_Timer`**:
   - `TIM2_Expired` 플래그 확인 후 비동기 음향 시퀀스(`Buzzer_Process_Timer()`) 진행.

3. **`[3] Process_Button_Event`**:
   - `btn_state` 인터럽트 상태에 따른 버튼 전용 핸들러 실행:
     - `Handle_Btn_Check()`: 디바운스 대기 후 `"Check\n"` 송신
     - `Handle_Btn_Pause()`: 디바운스 대기 후 `"Pause\n"` 또는 `"Resume\n"` 토글 송신
     - `Handle_Btn_Reset()`: 디바운스 대기 후 `"Reset\n"` 송신 및 0단계 리셋

4. **공통 헬퍼 함수**:
   - `Wait_Button_Release(btn_pin)`: 버튼 누름 후 바운싱 지연 및 손을 뗄 때까지 안정적 대기
   - `Reset_System_State(clear_fail_led)`: LED 소등, 버튼 인터럽트 비활성화, 상태 초기화 통합 헬퍼

---

## 3. 하드웨어 핀맵 (Pinout)

### 3.1 버튼 입력 (EXTI 인터럽트, Active Low)
- **BTN 0 (Check 버튼)**: `PB0` (누르면 Qt로 `"Check\n"` 송신 → AI 비전 판정 실행)
- **BTN 1 (Pause/Resume 버튼)**: `PB1` (토글 방식, 누르면 `"Pause\n"` 또는 `"Resume\n"` 송신)
- **BTN 2 (Reset 버튼)**: `PB2` (누르면 `"Reset\n"` 송신 → 불량 등록 및 초기화)

### 3.2 LED 출력
- **STEP 1 ~ STEP 9 LED**: `PC0` ~ `PC8` (각 단계 진행 시 해당 LED 점등, Active High)
- **FAIL LED**: `PC9` (AI 판정 FAIL 시 빨간색 경보 LED 점등)

### 3.3 부저 출력
- **Buzzer**: `PB13` (TIM2 기반 소프트웨어 주파수/타이밍 토글 제어)

### 3.4 통신 (USART2)
- **TX**: `PA2`
- **RX**: `PA3`
- Baudrate: `115200 bps`

---

## 4. 부저 사운드 명세 (상태별 6종 사운드)

현장 작업자가 화면을 보지 않고도 청각적으로 현재 상태를 인지할 수 있도록 6종의 고유 멜로디를 제공합니다:

| 상태 | 매크로 상수 | 멜로디 구성 | 설명 |
|:---|:---|:---|:---|
| **PASS** | `SOUND_PASS` | 2음 (상승음: 도-솔) | 단계 정상 완료 및 다음 단계 진입 |
| **FAIL** | `SOUND_FAIL` | 3음 (저음 경보: 낮은음 반복) | AI 판정 불량 경보 |
| **공정 완료** | `SOUND_COMPLETE` | 5음 (승리 팡파레) | 제품의 모든 STEP 조립 완료 |
| **수동 불량** | `SOUND_DEFECT` | 2음 (하강음: 솔-도) | 작업자 수동 불량 등록 및 리셋 |
| **일시정지** | `SOUND_PAUSE` | 2음 (미-도 단음) | 작업 일시정지 알림 |
| **작업재개** | `SOUND_RESUME` | 2음 (도-미 단음) | 작업 재개 알림 |

---

## 5. UART 통신 프로토콜

### 5.1 수신 명령 (Jetson Qt → STM32, 단일 문자)
- `'S'`: 작업 시작 (STEP 1 LED ON, 버튼 활성화)
- `'P'`: PASS (다음 STEP LED ON, PASS 부저)
- `'F'`: FAIL (FAIL LED ON, FAIL 부저)
- `'C'`: 전체 공정 완료 (LED 전체 소등, 완료 팡파레 부저, 대기 상태 복귀)
- `'R'`: 불량 등록/리셋 (LED 전체 소등, 불량 부저, 0단계 대기 상태 초기화)
- `'U'`: Qt GUI 일시정지 (STEP LED OFF, 일시정지 부저)
- `'M'`: Qt GUI 작업재개 (STEP LED ON, 작업재개 부저)
- `'E'`: 프로그램 종료/로그아웃 (전 LED 소등, 부저 정지, 버튼 인터럽트 비활성화)
- `'1'` ~ `'9'`: 서버 작업 복원 (해당 STEP n의 LED ON 및 버튼 활성화)

### 5.2 송신 명령 (STM32 → Jetson Qt, 문자열)
- `"Check\n"`: 버튼 0 누름 시 송신
- `"Pause\n"`: 버튼 1 누름 시 (진행 중일 때) 송신
- `"Resume\n"`: 버튼 1 누름 시 (일시정지 중일 때) 송신
- `"Reset\n"`: 버튼 2 누름 시 송신

---

## 6. 빌드 및 플래싱

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
