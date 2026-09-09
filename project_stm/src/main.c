#include "device_driver.h"
#include <stdio.h>
#include <string.h>

/* ── 전역 변수 및 외부 참조 ─────────────────────────────────────────── */

volatile uint8_t Uart_data[4];
volatile uint8_t Uart_Data_In = 0;

extern volatile btn_status_t btn_state;
extern volatile uint8_t is_pause;
extern volatile uint8_t TIM2_Expired;

volatile led_step_t led_step = LED_STEP0;

static const char *Uart_Tx_Dataset[] = {
	"Check\n",
	"Pause\n",
	"Resume\n",
	"Reset\n",
	"Start\n"
};

/* ── 함수 전방 선언 (Forward Declarations) ───────────────────────────── */

static void Sys_Init(int baud);
static void Process_Uart_Command(void);
static void Process_Buzzer_Timer(void);
static void Process_Button_Event(void);

/* =====================================================================
 *  [0] 메인 진입점 (Main Loop)
 *  while(1) 내부에서 3개의 핵심 프로세스 함수를 순차적으로 실행합니다.
 * ===================================================================== */

void Main(void)
{
	Sys_Init(115200);

	while (1)
	{
		Process_Uart_Command();  /* 1. UART 수신 명령 처리 */
		Process_Buzzer_Timer();   /* 2. 부저 재생 타이머 처리 */
		Process_Button_Event();   /* 3. 하드웨어 버튼 이벤트 처리 */
	}
}

/* =====================================================================
 *  [1] UART 명령 처리 프로세스 (Process_Uart_Command)
 * ===================================================================== */

static void Handle_Uart_Start(void);
static void Handle_Uart_Pass(void);
static void Handle_Uart_Fail(void);
static void Handle_Uart_Complete(void);
static void Handle_Uart_Defect(void);
static void Handle_Uart_Pause(void);
static void Handle_Uart_Resume(void);
static void Handle_Uart_Exit(void);
static void Handle_Uart_Restore(uint8_t target_step);

/**
 * @brief 수신된 UART 명령어를 파싱하여 상태 및 LED/부저를 제어합니다.
 */
static void Process_Uart_Command(void)
{
	if (!Uart_Data_In)
		return;

	char cmd = Uart_data[0];

	switch (cmd)
	{
	case 'S': Handle_Uart_Start(); break;
	case 'P': Handle_Uart_Pass(); break;
	case 'F': Handle_Uart_Fail(); break;
	case 'C': Handle_Uart_Complete(); break;
	case 'R': Handle_Uart_Defect(); break;
	case 'U': Handle_Uart_Pause(); break;
	case 'M': Handle_Uart_Resume(); break;
	case 'E': Handle_Uart_Exit(); break;
	case '1':
	case '2':
	case '3':
	case '4':
	case '5':
	case '6':
	case '7':
	case '8':
	case '9':
		Handle_Uart_Restore(cmd - '0');
		break;
	default:
		break;
	}

	Uart_Data_In = 0;
}

static void Reset_System_State(uint8_t clear_fail_led);

static void Handle_Uart_Start(void)
{
	Btn_ISR_Enable(0, 1, 1, 1);
	led_step = LED_STEP1;
	Step_LED_On(led_step);
	Fail_LED_Off();
	if (!Buzzer_Is_Playing())
	{
		Buzzer_Play(SOUND_START);
	}
	is_pause = 0;
}

static void Handle_Uart_Pass(void)
{
	if (led_step == LED_STEP0)
		return;

	Fail_LED_Off();
	is_pause = 0;
	Step_LED_Off(led_step);
	led_step = (led_step + 1) % 10;
	Step_LED_On(led_step);
	Buzzer_Play(SOUND_PASS);
}

static void Handle_Uart_Fail(void)
{
	Fail_LED_On();
	is_pause = 0;
	Buzzer_Play(SOUND_FAIL);
}

static void Handle_Uart_Complete(void)
{
	Reset_System_State(0);
	Buzzer_Play(SOUND_COMPLETE);
}

static void Handle_Uart_Defect(void)
{
	Reset_System_State(0);
	Buzzer_Play(SOUND_DEFECT);
}

static void Handle_Uart_Pause(void)
{
	if (led_step != LED_STEP0 && is_pause == 0)
	{
		is_pause = 1;
		Step_LED_Off(led_step);
		Btn_ISR_Enable(0, 0, 1, 1);
		Buzzer_Play(SOUND_PAUSE);
	}
}

static void Handle_Uart_Resume(void)
{
	if (led_step != LED_STEP0 && is_pause == 1)
	{
		is_pause = 0;
		Step_LED_On(led_step);
		Btn_ISR_Enable(0, 1, 1, 1);
		Buzzer_Play(SOUND_RESUME);
	}
}

static void Handle_Uart_Exit(void)
{
	Reset_System_State(1);
	Buzzer_Stop();
}

static void Handle_Uart_Restore(uint8_t target_step)
{
	Fail_LED_Off();
	Buzzer_Stop();
	if (led_step != LED_STEP0)
	{
		Step_LED_Off(led_step);
	}
	Macro_Clear_Area(GPIOC->ODR, 0x1ff, 0);
	led_step = (led_step_t)target_step;
	is_pause = 0;
	btn_state = BTN_RELEASED;
	Step_LED_On(led_step);
	Btn_ISR_Enable(0, 1, 1, 1);
}

/* =====================================================================
 *  [2] 부저 재생 타이머 프로세스 (Process_Buzzer_Timer)
 * ===================================================================== */

/**
 * @brief TIM2 만료 주기에 맞춰 부저 음향 시퀀스를 진행합니다.
 */
static void Process_Buzzer_Timer(void)
{
	if (!TIM2_Expired)
		return;

	TIM2_Expired = 0;
	Buzzer_Process_Timer();
}

/* =====================================================================
 *  [3] 버튼 이벤트 처리 프로세스 (Process_Button_Event)
 * ===================================================================== */

static void Handle_Btn_Start(void);
static void Handle_Btn_Check(void);
static void Handle_Btn_Pause(void);
static void Handle_Btn_Reset(void);
static void Wait_Button_Release(uint8_t btn_pin);

/**
 * @brief 하드웨어 버튼 누름 인터럽트 이벤트를 처리합니다.
 */
static void Process_Button_Event(void)
{
	switch (btn_state)
	{
	case BTN_RELEASED:
		break;
	case BTN_START_PRESSED:
		Handle_Btn_Start();
		break;
	case BTN_CHECK_PRESSED:
		Handle_Btn_Check();
		break;
	case BTN_PAUSE_PRESSED:
		Handle_Btn_Pause();
		break;
	case BTN_RESET_PRESSED:
		Handle_Btn_Reset();
		break;
	default:
		btn_state = BTN_RELEASED;
		break;
	}
}

static void Handle_Btn_Start(void)
{
	if (led_step != LED_STEP0)
	{
		btn_state = BTN_RELEASED;
		Wait_Button_Release(BTN_START);
		Btn_ISR_Enable(0, !is_pause, 1, 1);
		return;
	}

	Btn_ISR_Enable(0, 0, 0, 0);
	Uart2_Send_String(Uart_Tx_Dataset[4]);
	Buzzer_Play(SOUND_START);
	Wait_Button_Release(BTN_START);
	btn_state = BTN_RELEASED;
}

static void Handle_Btn_Check(void)
{
	if (is_pause || led_step == LED_STEP0)
	{
		btn_state = BTN_RELEASED;
		Btn_ISR_Enable(0, !is_pause, 1, 1);
		return;
	}

	/* 버튼 감지 즉시 UART 메시지를 전송하여 Jetson이 대기 시간 없이 즉시 캡처/추론을 시작합니다. */
	Uart2_Send_String(Uart_Tx_Dataset[0]);
	Wait_Button_Release(BTN_CHECK);
	btn_state = BTN_RELEASED;
}

static void Handle_Btn_Pause(void)
{
	if (led_step == LED_STEP0)
	{
		btn_state = BTN_RELEASED;
		EXTI->PR = (0x1 << BTN_PAUSE);
		NVIC_ClearPendingIRQ(BTN_PAUSE_IRQN);
		Macro_Set_Bit(EXTI->IMR, BTN_PAUSE);
		NVIC_EnableIRQ(BTN_PAUSE_IRQN);
		return;
	}

	if (is_pause == 0)
	{
		is_pause = 1;
		Uart2_Send_String(Uart_Tx_Dataset[1]);
		Step_LED_Off(led_step);
		Btn_ISR_Enable(0, 0, 1, 1);
		Buzzer_Play(SOUND_PAUSE);
	}
	else
	{
		is_pause = 0;
		Uart2_Send_String(Uart_Tx_Dataset[2]);
		Step_LED_On(led_step);
		Btn_ISR_Enable(0, 1, 1, 1);
		Buzzer_Play(SOUND_RESUME);
	}

	Wait_Button_Release(BTN_PAUSE);

	btn_state = BTN_RELEASED;
	EXTI->PR = (0x1 << BTN_PAUSE);
	NVIC_ClearPendingIRQ(BTN_PAUSE_IRQN);
	Macro_Set_Bit(EXTI->IMR, BTN_PAUSE);
	NVIC_EnableIRQ(BTN_PAUSE_IRQN);
}

static void Handle_Btn_Reset(void)
{
	Btn_ISR_Enable(0, 0, 0, 0);
	Uart2_Send_String(Uart_Tx_Dataset[3]);
	Reset_System_State(0);
	Buzzer_Play(SOUND_DEFECT);
	Wait_Button_Release(BTN_RESET);
}

/* =====================================================================
 *  [4] 공통 초기화 및 헬퍼 함수
 * ===================================================================== */

static void Sys_Init(int baud)
{
	SCB->CPACR |= (0x3 << 10 * 2) | (0x3 << 11 * 2);
	Clock_Init();
	Uart2_Init(baud);
	setvbuf(stdout, NULL, _IONBF, 0);
	LED_Init();
	UART2_RX_Interrupt_Enable(1);
	Buzzer_Init();
	Macro_Set_Bit(RCC->APB1ENR, 0); // TIM2 Clock Enable
	Reset_System_State(1);
}

/**
 * @brief 버튼 누름 후 바운싱 지연 및 손을 뗄 때까지 대기합니다.
 */
static void Wait_Button_Release(uint8_t btn_pin)
{
	for (volatile int d = 0; d < 300000; d++);
	int timeout = 5000000;
	while (!Macro_Check_Bit_Set(GPIOB->IDR, btn_pin) && --timeout > 0);
	for (volatile int d = 0; d < 200000; d++);
}

/**
 * @brief 시스템의 LED 소등, 버튼 인터럽트 비활성화 및 공정 상태를 0단계로 초기화합니다.
 * @param clear_fail_led 1이면 FAIL LED를 포함한 전 LED(0x3ff) 소등, 0이면 STEP LED(0x1ff) 소등
 */
static void Reset_System_State(uint8_t clear_fail_led)
{
	Fail_LED_Off();
	if (led_step != LED_STEP0)
	{
		Step_LED_Off(led_step);
	}
	Macro_Clear_Area(GPIOC->ODR, clear_fail_led ? 0x3ff : 0x1ff, 0);
	led_step = LED_STEP0;
	btn_state = BTN_RELEASED;
	is_pause = 0;
	Btn_ISR_Enable(1, 0, 0, 0);
}