#include "timer.h"

volatile uint8_t TIM2_Expired = 0;

void TIM3_Out_Init(void)
{
	Macro_Set_Bit(RCC->AHB1ENR, 1);
	Macro_Set_Bit(RCC->APB1ENR, 1);

	Macro_Write_Block(GPIOB->MODER, 0x3, 0x1, 0);  	// PB0 => Output
	Macro_Clear_Bit(GPIOB->OTYPER, 0);
	Macro_Clear_Bit(GPIOB->ODR, 0);                 // PB0 = 0 (LOW)

	Macro_Write_Block(GPIOB->AFR[0], 0xf, 0x2, 0); 	// PB0 => AF02

	Macro_Write_Block(TIM3->CCMR2, 0xff, 0x60, 0);
	TIM3->CCER = (0<<9)|(0<<8);                     // CC3E = 0 initially
	TIM3->CCR3 = 0;
	TIM3->CR1 = 0;
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
	Macro_Clear_Bit(TIM2->CR1, 0);
	NVIC_ClearPendingIRQ(28);
	
	TIM2_Expired = 1;
}



void TIM3_Freq_Generation_DR50(unsigned short freq)
{
	if (freq == 0)
	{
		TIM3_Out_Stop();
		return;
	}

	Macro_Write_Block(GPIOB->MODER, 0x3, 0x2, 0);  	// PB0 => ALT
	Macro_Write_Block(GPIOB->AFR[0], 0xf, 0x2, 0); 	// PB0 => AF02
	TIM3->CCER |= (1 << 8);                         // CC3E = 1

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
	TIM3->CR1 &= ~(1 << 0);
	TIM3->CCR3 = 0;
	TIM3->EGR |= (1 << 0);
	TIM3->CCER &= ~(1 << 8);

	Macro_Write_Block(GPIOB->MODER, 0x3, 0x1, 0);  	// PB0 => Output
	Macro_Clear_Bit(GPIOB->ODR, 0);                 // PB0 = 0 (LOW)
}

