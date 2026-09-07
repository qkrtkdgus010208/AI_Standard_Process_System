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
}

volatile uint8_t Uart_data[4];
volatile uint8_t Uart_Data_In = 0;


extern volatile btn_status_t btn_state;
extern volatile uint8_t is_pause;
extern volatile uint8_t TIM2_Expired;

static const unsigned int Max_Step_Array[NUM_OF_PRODUCT] = {9, 10};

void Main(void)
{
	uint8_t fail_in = 0;
	uint8_t fail_task_cnt = 0;
	uint8_t pass_stage = 0;
	uint8_t pass_task_cnt = 0;
	static const char *Uart_Tx_Dataset[] = {"Check\n", "Pause\n", "Resume\n", "Reset\n"};
	led_step_t led_step = LED_STEP0;


	Sys_Init(115200);
	printf("Buzzer Test!!\n");

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
				break;

			case 'P':
				if (led_step == LED_STEP0)
					break;

				pass_stage = 1;
				Step_LED_Off(led_step);
				led_step = (led_step + 1) % 10;
				Step_LED_On(led_step);

				Btn_ISR_Enable(1, 1, 1);
				break;

			case 'F':
				fail_in = 1;
				break;
			default:
				break;
			}

			Uart_Data_In = 0;
		}

		if (TIM2_Expired)
		{
			printf("%d\n", pass_task_cnt);
			if (pass_stage)
				pass_task_cnt++;

			else if (fail_in)
				fail_task_cnt++;

			TIM2_Expired = 0;
		}

		if (fail_in && Macro_Check_Bit_Clear(TIM2->CR1, 0))
		{
			Fail_LED_Buzzer(&fail_in, &fail_task_cnt);
		}
		else if (pass_stage && Macro_Check_Bit_Clear(TIM2->CR1, 0))
		{
			Pass_Buzzer(pass_task_cnt);
			if(pass_task_cnt >= 3)
			{
				printf("Init!!!\n");
				pass_stage = 0;
				pass_task_cnt = 0;
			}
		}

		switch (btn_state)
		{
		case BTN_RELEASED:
			break;

		case BTN_CHECK_PRESSED:
			Uart2_Send_String(Uart_Tx_Dataset[0]);
			btn_state = BTN_RELEASED;
			break;

		case BTN_PAUSE_PRESSED:
			if(is_pause)
			{
				Btn_ISR_Enable(0, 1, 0);	
				Uart2_Send_String(Uart_Tx_Dataset[1]);
				Step_LED_Off(led_step);
			}

			else
			{
				Uart2_Send_String(Uart_Tx_Dataset[2]);
				Step_LED_On(led_step);
				Btn_ISR_Enable(1, 1, 1);
			}
			btn_state = BTN_RELEASED;
			break;

		case BTN_RESET_PRESSED:
			Btn_ISR_Enable(0, 0, 0);
			Uart2_Send_String(Uart_Tx_Dataset[3]);
			Step_LED_Off(led_step);
			led_step = LED_STEP0;
			btn_state = BTN_RELEASED;
			pass_stage = 0;
			pass_task_cnt = 0;
			fail_in = 0;
			fail_task_cnt = 0;
			break;
		}
	}
}

void Fail_LED_Buzzer(uint8_t *fail_in, uint8_t *fail_task_cnt)
{
	if ((*fail_task_cnt) % 2 == 0)
	{
		Fail_LED_On();
		Wrong_Sound();
		Buzzer_Delay_ms(200);
	}
	else
	{
		printf("%d\n", *fail_task_cnt);
		Fail_LED_Off();
		Buzzer_Stop();

		if (*fail_task_cnt < 5)
			Buzzer_Delay_ms(200);
		else
		{
			*fail_task_cnt = 0;
			*fail_in = 0;
		}
	}
}

void Pass_Buzzer(uint8_t pass_task_cnt)
{
	// printf("%d\n", pass_task_cnt);
	switch (pass_task_cnt)
	{
		case 0:
			Correct_Sound(1047);
			Buzzer_Delay_ms(120);
			break;

		case 1:
			Buzzer_Stop();
			Buzzer_Delay_ms(40);
			break;

		case 2:
			Correct_Sound(784);
			Buzzer_Delay_ms(350);
			break;
		case 3:
			Buzzer_Stop();
			break;
	// case 0:
	// 	Correct_Sound(523);
	// 	Buzzer_Delay_ms(120);
	// 	break;
	// case 1:
	// 	Correct_Sound(659);
	// 	Buzzer_Delay_ms(120);
	// 	break;
	// case 2:
	// 	Correct_Sound(784);
	// 	Buzzer_Delay_ms(120);
	// 	break;
	// default :
	// 	Buzzer_Stop();
	// 	break;
	
	
	}
}