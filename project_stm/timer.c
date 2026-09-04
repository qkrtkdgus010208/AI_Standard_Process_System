#include "timer.h"

volatile uint8_t TIM2_Expired = 0;

void TIM3_Out_Init(void)
{
	Macro_Set_Bit(RCC->AHB1ENR, 1);
	Macro_Set_Bit(RCC->APB1ENR, 1);

	Macro_Write_Block(GPIOB->MODER, 0x3, 0x2, 0);  	// PB0 => ALT
	Macro_Write_Block(GPIOB->AFR[0], 0xf, 0x2, 0); 	// PB0 => AF02

	Macro_Write_Block(TIM3->CCMR2,0xff, 0x60, 0);
	TIM3->CCER = (0<<9)|(1<<8);
}



void TIM2_Delay_Interrupt_Enable(int en, int time)
{
	if(en)
	{
		Macro_Set_Bit(RCC->APB1ENR, 0);

		NVIC_DisableIRQ(TIM2_IRQn);
        Macro_Clear_Bit(TIM2->DIER, 0);
        Macro_Clear_Bit(TIM2->CR1, 0);

		TIM2_Expired = 0;

		TIM2->CR1 = (1<<4)|(1<<3);
		TIM2->PSC = (unsigned int)(TIMXCLK/TIM2_FREQ + 0.5)-1;
		TIM2->ARR = TIME2_PLS_OF_1ms * time;
		Macro_Set_Bit(TIM2->EGR,0);

		Macro_Clear_Bit(TIM2->SR, 0);
		NVIC_ClearPendingIRQ(28);

		Macro_Set_Bit(TIM2->DIER, 0);
		NVIC_EnableIRQ(28);

		Macro_Set_Bit(TIM2->CR1, 0);
	}

	else
	{
		NVIC_DisableIRQ(28);
		Macro_Clear_Bit(TIM2->DIER, 0);
		Macro_Clear_Bit(TIM2->CR1, 0);

		Macro_Clear_Bit(TIM2->SR, 0);
		NVIC_ClearPendingIRQ(TIM2_IRQn);
		
	}
}


void TIM2_IRQHandler(void)
{
	Macro_Clear_Bit(TIM2->DIER, 0);
	Macro_Clear_Bit(TIM2->SR, 0);
	NVIC_ClearPendingIRQ(28);
	
	TIM2_Expired = 1;
}



void TIM3_Freq_Generation_DR50(unsigned short freq)
{
	TIM3->CR1 &= ~((0x1 << 7) | (0x1 << 4) | (0x1 << 3) | (0x1 << 0));

	// Timer 주파수가 TIM3_FREQ가 되도록 PSC 설정
	TIM3 -> PSC = (unsigned int)((double)TIMXCLK / TIM3_FREQ + 0.5) - 1;
	// 요청한 주파수가 되도록 ARR 설정
	TIM3 -> ARR = (unsigned int)(TIM3_FREQ / freq + 0.5) - 1;
	// Duty Rate 50%가 되도록 CCR3 설정
	TIM3 -> CCR3 = (TIM3 -> ARR) / 2;
	// Manual Update(UG 발생)
	TIM3 -> EGR |= 0x1 << 0;
	// Up Counter, Repeat Mode, Timer Start
	TIM3 -> CR1 |= (0x1 << 0);

}


void TIM3_Out_Stop(void)
{
	TIM3->CCR3 = 0;
	Macro_Set_Bit(TIM3->EGR, 0);
	
	Macro_Clear_Bit(TIM3->CR1, 0);
}


#if 0
int TIM4_Check_Timeout(void)
{
	if(Macro_Check_Bit_Set(TIM4->SR, 0))
	{
		Macro_Clear_Bit(TIM4->SR, 0);
		return 1;
	}
	else
	{
		return 0;
	}
}

void TIM4_Stop(void)
{
	Macro_Clear_Bit(TIM4->CR1, 0);
}

void TIM4_Change_Value(int time)
{
	TIM4->ARR = TIME4_PLS_OF_1ms * time;
}

void TIM4_Repeat(int time)
{
	Macro_Set_Bit(RCC->APB1ENR, 2);

	TIM4->CR1 = (1<<4)|(0<<3);
	TIM4->PSC = (unsigned int)(TIMXCLK/(double)TIM4_FREQ + 0.5)-1;
	TIM4->ARR = TIME4_PLS_OF_1ms * time - 1;

	Macro_Set_Bit(TIM4->EGR,0);
	Macro_Clear_Bit(TIM4->SR, 0);
	Macro_Set_Bit(TIM4->CR1, 0);
}

#endif

#if 0
void TIM2_Stopwatch_Start(void)
{
	Macro_Set_Bit(RCC->APB1ENR, 0);

	TIM2->CR1 = (1<<4)|(1<<3);
	TIM2->PSC = (unsigned int)(TIMXCLK/50000.0 + 0.5)-1;
	TIM2->ARR = TIM2_MAX;

	Macro_Set_Bit(TIM2->EGR,0);
	Macro_Set_Bit(TIM2->CR1, 0);
}

unsigned int TIM2_Stopwatch_Stop(void)
{
	unsigned int time;

	Macro_Clear_Bit(TIM2->CR1, 0);
	time = (TIM2_MAX - TIM2->CNT) * TIM2_TICK;
	return time;
}
#endif

#if 0
/* Delay Time Max = 65536 * 20use = 1.3sec */
void TIM2_Delay(int time)
{
	Macro_Set_Bit(RCC->APB1ENR, 0);

	TIM2->CR1 = (1<<4)|(1<<3);
	TIM2->PSC = (unsigned int)(TIMXCLK/TIM2_FREQ + 0.5)-1;
	TIM2->ARR = TIME2_PLS_OF_1ms * time;

	Macro_Set_Bit(TIM2->EGR,0);
	Macro_Clear_Bit(TIM2->SR, 0);
	Macro_Set_Bit(TIM2->CR1, 0);

	while(Macro_Check_Bit_Clear(TIM2->SR, 0));

	Macro_Clear_Bit(TIM2->CR1, 0);
}


/* Delay Time Extended */
void TIM2_Delay(int time)
{
	int i;
	unsigned int t = TIME2_PLS_OF_1ms * time;

	Macro_Set_Bit(RCC->APB1ENR, 0);

	TIM2->PSC = (unsigned int)(TIMXCLK/(double)TIM2_FREQ + 0.5)-1;
	TIM2->CR1 = (1<<4)|(1<<3);
	TIM2->ARR = 0xffff;
	Macro_Set_Bit(TIM2->EGR,0);

	for(i=0; i<(t/0xffffu); i++)
	{
		Macro_Set_Bit(TIM2->EGR,0);
		Macro_Clear_Bit(TIM2->SR, 0);
		Macro_Set_Bit(TIM2->CR1, 0);
		while(Macro_Check_Bit_Clear(TIM2->SR, 0));
	}

	TIM2->ARR = t % 0xffffu;
	Macro_Set_Bit(TIM2->EGR,0);
	Macro_Clear_Bit(TIM2->SR, 0);
	Macro_Set_Bit(TIM2->CR1, 0);
	while (Macro_Check_Bit_Clear(TIM2->SR, 0));

	Macro_Clear_Bit(TIM2->CR1, 0);
}

#endif

#if 0
void TIM3_Out_PWM_Generation(unsigned short freq, int duty)
{
	TIM3 -> CR1 |= (0x0 << 7) | (0x0 << 3) | (0x0 << 0);
	TIM3 -> CR1 &= ~(0x1 << 4);
	// Timer 주파수가 TIM3_FREQ가 되도록 PSC 설정
	TIM3 -> PSC = (int)((double)TIMXCLK / TIM3_FREQ + 0.5) - 1;
	// 요청한 주파수가 되도록 ARR 설정
	TIM3 -> ARR = (unsigned int)(TIM3_FREQ / freq + 0.5) - 1;
	// Duty Rate 50%가 되도록 CCR3 설정
	TIM3 -> CCR3 = (unsigned int)((TIM3 -> ARR) * (duty / 100.));
	// Manual Update(UG 발생)
	TIM3 -> EGR |= 0x1 << 0;
	// Down Counter, Repeat Mode, Timer Start
	TIM3 -> CR1 |= (0x1 << 0);

}




void TIM3_Out_Freq_Generation(unsigned short freq)
{
	TIM3 -> CR1 |= (0x0 << 7) | (0x1 << 4) | (0x0 << 3) | (0x0 << 0);
	// Timer 주파수가 TIM3_FREQ가 되도록 PSC 설정
	TIM3 -> PSC = (unsigned int)((double)TIMXCLK / TIM3_FREQ + 0.5) - 1;
	// 요청한 주파수가 되도록 ARR 설정
	TIM3 -> ARR = (unsigned int)(TIM3_FREQ / freq + 0.5) - 1;
	// Duty Rate 50%가 되도록 CCR3 설정
	TIM3 -> CCR3 = (TIM3 -> ARR) / 2;
	// Manual Update(UG 발생)
	TIM3 -> EGR |= 0x1 << 0;
	// Down Counter, Repeat Mode, Timer Start
	TIM3 -> CR1 |= (0x1 << 0);

}

#endif