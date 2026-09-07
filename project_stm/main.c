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
	TIM3_Out_Init();
	Macro_Set_Bit(RCC->APB1ENR, 0); // TIM2 Clock Enable
}

volatile uint8_t Uart_data[4];
volatile uint8_t Uart_Data_In = 0;


extern volatile btn_status_t btn_state;
extern volatile uint8_t is_pause;
extern volatile uint8_t TIM2_Expired;


void Main(void)
{
	volatile uint8_t fail_in = 0;
	volatile uint8_t fail_task_cnt = 0;
	volatile uint8_t pass_stage = 0;
	volatile uint8_t pass_task_cnt = 0;
	static const char *Uart_Tx_Dataset[] = {"Check\n", "Pause\n", "Resume\n", "Reset\n"};
	led_step_t led_step = LED_STEP0;


	Sys_Init(115200);
	// printf("Buzzer Test!!\n");

	while (1)
	{
		if (Uart_Data_In)
		{
			switch (Uart_data[0])
			{
			case 'S':
				Btn_ISR_Enable(1, 1, 1);
				led_step = LED_STEP1;
				Step_LED_On(led_step);
				Fail_LED_Off();
				Buzzer_Stop();
				TIM2_Delay_Interrupt_Enable(0, 0);
				pass_stage = 0;
				pass_task_cnt = 0;
				fail_in = 0;
				fail_task_cnt = 0;
				is_pause = 0;
				TIM2_Expired = 0;
				break;

			case 'P':
				if (led_step == LED_STEP0)
					break;

				Fail_LED_Off();
				fail_in = 0;
				fail_task_cnt = 0;
				is_pause = 0;

				Step_LED_Off(led_step);
				led_step = (led_step + 1) % 10;
				Step_LED_On(led_step);

				// 부저 재생 중 버튼 인터럽트 차단 (채터링 및 중복 Check 전송 방지)
				Btn_ISR_Enable(0, 0, 0);

				Buzzer_Stop();
				TIM2_Delay_Interrupt_Enable(0, 0);

				pass_stage = 1;
				pass_task_cnt = 0;
				TIM2_Expired = 0;
				Correct_Sound(1047);
				Buzzer_Delay_ms(120);
				break;

			case 'F':
				pass_stage = 0;
				pass_task_cnt = 0;
				fail_in = 1;
				fail_task_cnt = 0;
				is_pause = 0;
				TIM2_Expired = 0;

				Fail_LED_On();
				Btn_ISR_Enable(0, 0, 0);

				Buzzer_Stop();
				TIM2_Delay_Interrupt_Enable(0, 0);
				Wrong_Sound();
				Buzzer_Delay_ms(250);
				break;

			case 'R':
				Btn_ISR_Enable(0, 0, 0);
				Step_LED_Off(led_step);
				led_step = LED_STEP0;
				btn_state = BTN_RELEASED;
				pass_stage = 0;
				pass_task_cnt = 0;
				fail_in = 0;
				fail_task_cnt = 0;
				is_pause = 0;
				TIM2_Expired = 0;
				Fail_LED_Off();
				Buzzer_Stop();
				TIM2_Delay_Interrupt_Enable(0, 0);
				break;

			default:
				break;
			}

			Uart_Data_In = 0;
		}

		if (TIM2_Expired)
		{
			TIM2_Expired = 0;

			if (pass_stage)
			{
				pass_task_cnt++;
				Pass_Buzzer(pass_task_cnt);
				if (pass_task_cnt >= 3)
				{
					pass_stage = 0;
					pass_task_cnt = 0;
					Buzzer_Stop();
					TIM2_Delay_Interrupt_Enable(0, 0);
					Btn_ISR_Enable(1, 1, 1);
				}
			}
			else if (fail_in)
			{
				fail_task_cnt++;
				Fail_LED_Buzzer(fail_task_cnt);
				if (fail_task_cnt >= 3)
				{
					fail_in = 0;
					fail_task_cnt = 0;
					Buzzer_Stop();
					TIM2_Delay_Interrupt_Enable(0, 0);
					Btn_ISR_Enable(1, 1, 1);
				}
			}
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
			for (volatile int d = 0; d < 300000; d++);
			int timeout_check = 5000000;
			while (!Macro_Check_Bit_Set(GPIOB->IDR, BTN_CHECK) && --timeout_check > 0);
			for (volatile int d = 0; d < 200000; d++);

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

			// 디바운스 및 버튼 릴리즈 대기
			for (volatile int d = 0; d < 300000; d++);
			int timeout_pause = 5000000;
			while (!Macro_Check_Bit_Set(GPIOB->IDR, BTN_PAUSE) && --timeout_pause > 0);
			for (volatile int d = 0; d < 200000; d++);

			if (is_pause == 0)
			{
				is_pause = 1;
				Buzzer_Stop();
				TIM2_Delay_Interrupt_Enable(0, 0);
				pass_stage = 0;
				pass_task_cnt = 0;
				Uart2_Send_String(Uart_Tx_Dataset[1]);
				Step_LED_Off(led_step);
				Btn_ISR_Enable(0, 1, 1);
			}
			else
			{
				is_pause = 0;
				Uart2_Send_String(Uart_Tx_Dataset[2]);
				Step_LED_On(led_step);
				Btn_ISR_Enable(1, 1, 1);
			}

			btn_state = BTN_RELEASED;
			EXTI->PR = (0x1 << BTN_PAUSE);
			NVIC_ClearPendingIRQ(BTN_PAUSE_IRQN);
			Macro_Set_Bit(EXTI->IMR, BTN_PAUSE);
			NVIC_EnableIRQ(BTN_PAUSE_IRQN);
			break;

		case BTN_RESET_PRESSED:
			Btn_ISR_Enable(0, 0, 0);
			for (volatile int d = 0; d < 300000; d++);
			int timeout_reset = 5000000;
			while (!Macro_Check_Bit_Set(GPIOB->IDR, BTN_RESET) && --timeout_reset > 0);
			for (volatile int d = 0; d < 200000; d++);

			Uart2_Send_String(Uart_Tx_Dataset[3]);
			Step_LED_Off(led_step);
			led_step = LED_STEP0;
			btn_state = BTN_RELEASED;
			pass_stage = 0;
			pass_task_cnt = 0;
			fail_in = 0;
			fail_task_cnt = 0;
			is_pause = 0;
			TIM2_Expired = 0;
			Fail_LED_Off();
			Buzzer_Stop();
			TIM2_Delay_Interrupt_Enable(0, 0);
			break;
		}
	}
}

void Fail_LED_Buzzer(uint8_t fail_task_cnt)
{
	switch (fail_task_cnt)
	{
	case 0:
		break;

	case 1:
		Buzzer_Stop();
		Buzzer_Delay_ms(100);
		break;

	case 2:
		Wrong_Sound();
		Buzzer_Delay_ms(250);
		break;

	case 3:
	default:
		Buzzer_Stop();
		break;
	}
}

void Pass_Buzzer(uint8_t pass_task_cnt)
{
	switch (pass_task_cnt)
	{
	case 0:
		break;

	case 1:
		Buzzer_Stop();
		Buzzer_Delay_ms(60);
		break;

	case 2:
		Correct_Sound(784);
		Buzzer_Delay_ms(200);
		break;

	case 3:
	default:
		Buzzer_Stop();
		break;
	}
}