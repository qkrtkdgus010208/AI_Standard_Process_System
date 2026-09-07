#include "device_driver.h"
#include <stdio.h>
#include <string.h>

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
}

volatile uint8_t Uart_data[4];
volatile uint8_t Uart_Data_In = 0;

extern volatile btn_status_t btn_state;
extern volatile uint8_t is_pause;
extern volatile uint8_t TIM2_Expired;

volatile led_step_t led_step = LED_STEP0;

/* ── 중복 코드 제거를 위한 정적 헬퍼 함수 ───────────────────────────── */

/**
 * @brief 버튼 누름 후 바운싱 안정화 및 손을 뗄 때까지 대기합니다.
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
	Btn_ISR_Enable(0, 0, 0);
}

void Main(void)
{
	static const char *Uart_Tx_Dataset[] = {"Check\n", "Pause\n", "Resume\n", "Reset\n"};

	Sys_Init(115200);

	while (1)
	{
		if (Uart_Data_In)
		{
			switch (Uart_data[0])
			{
			case 'S': // 작업 시작
				Btn_ISR_Enable(1, 1, 1);
				led_step = LED_STEP1;
				Step_LED_On(led_step);
				Fail_LED_Off();
				Buzzer_Stop();
				is_pause = 0;
				break;

			case 'P': // PASS (다음 STEP 진입)
				if (led_step == LED_STEP0)
					break;

				Fail_LED_Off();
				is_pause = 0;
				Step_LED_Off(led_step);
				led_step = (led_step + 1) % 10;
				Step_LED_On(led_step);
				Buzzer_Play(SOUND_PASS);
				break;

			case 'F': // FAIL
				Fail_LED_On();
				is_pause = 0;
				Buzzer_Play(SOUND_FAIL);
				break;

			case 'C': // 모든 STEP 완료 / 작업 정상 종료
				Reset_System_State(0);
				Buzzer_Play(SOUND_COMPLETE);
				break;

			case 'R': // 불량 등록 / 리셋
				Reset_System_State(0);
				Buzzer_Play(SOUND_DEFECT);
				break;

			case 'U': // Qt GUI에서 일시정지 명령
				if (led_step != LED_STEP0 && is_pause == 0)
				{
					is_pause = 1;
					Step_LED_Off(led_step);
					Btn_ISR_Enable(0, 1, 1);
					Buzzer_Play(SOUND_PAUSE);
				}
				break;

			case 'M': // Qt GUI에서 작업재개 명령
				if (led_step != LED_STEP0 && is_pause == 1)
				{
					is_pause = 0;
					Step_LED_On(led_step);
					Btn_ISR_Enable(1, 1, 1);
					Buzzer_Play(SOUND_RESUME);
				}
				break;

			case 'E': // Qt 프로그램 종료 / 로그아웃 (전체 종료 및 대기 상태)
				Reset_System_State(1);
				Buzzer_Stop();
				break;

			case '1':
			case '2':
			case '3':
			case '4':
			case '5':
			case '6':
			case '7':
			case '8':
			case '9': // 서버에서 복원된 작업 상태 반영 (해당 STEP LED 점등 및 활성화)
				Fail_LED_Off();
				Buzzer_Stop();
				if (led_step != LED_STEP0)
				{
					Step_LED_Off(led_step);
				}
				Macro_Clear_Area(GPIOC->ODR, 0x1ff, 0);
				led_step = (led_step_t)(Uart_data[0] - '0');
				is_pause = 0;
				btn_state = BTN_RELEASED;
				Step_LED_On(led_step);
				Btn_ISR_Enable(1, 1, 1);
				break;

			default:
				break;
			}

			Uart_Data_In = 0;
		}

		if (TIM2_Expired)
		{
			TIM2_Expired = 0;
			Buzzer_Process_Timer();
		}

		switch (btn_state)
		{
		case BTN_RELEASED:
			break;

		case BTN_CHECK_PRESSED:
			if (is_pause || led_step == LED_STEP0)
			{
				btn_state = BTN_RELEASED;
				Btn_ISR_Enable(!is_pause, 1, 1);
				break;
			}
			Wait_Button_Release(BTN_CHECK);
			Uart2_Send_String(Uart_Tx_Dataset[0]);
			btn_state = BTN_RELEASED;
			break;

		case BTN_PAUSE_PRESSED:
			if (led_step == LED_STEP0)
			{
				btn_state = BTN_RELEASED;
				EXTI->PR = (0x1 << BTN_PAUSE);
				NVIC_ClearPendingIRQ(BTN_PAUSE_IRQN);
				Macro_Set_Bit(EXTI->IMR, BTN_PAUSE);
				NVIC_EnableIRQ(BTN_PAUSE_IRQN);
				break;
			}

			Wait_Button_Release(BTN_PAUSE);

			if (is_pause == 0)
			{
				is_pause = 1;
				Uart2_Send_String(Uart_Tx_Dataset[1]);
				Step_LED_Off(led_step);
				Btn_ISR_Enable(0, 1, 1);
				Buzzer_Play(SOUND_PAUSE);
			}
			else
			{
				is_pause = 0;
				Uart2_Send_String(Uart_Tx_Dataset[2]);
				Step_LED_On(led_step);
				Btn_ISR_Enable(1, 1, 1);
				Buzzer_Play(SOUND_RESUME);
			}

			btn_state = BTN_RELEASED;
			EXTI->PR = (0x1 << BTN_PAUSE);
			NVIC_ClearPendingIRQ(BTN_PAUSE_IRQN);
			Macro_Set_Bit(EXTI->IMR, BTN_PAUSE);
			NVIC_EnableIRQ(BTN_PAUSE_IRQN);
			break;

		case BTN_RESET_PRESSED:
			Btn_ISR_Enable(0, 0, 0);
			Wait_Button_Release(BTN_RESET);
			Uart2_Send_String(Uart_Tx_Dataset[3]);
			Reset_System_State(0);
			Buzzer_Play(SOUND_DEFECT);
			break;
		}
	}
}