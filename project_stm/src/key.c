#include "key.h"

void Btn_ISR_Enable(int start_en, int check_en, int pause_en, int reset_en)
{
	Macro_Set_Bit(RCC->AHB1ENR, 1);
	Macro_Write_Block(GPIOB->MODER, 0xff, 0x00, 2 * BTN_START);
	Macro_Write_Block(GPIOB->PUPDR, 0xff, 0x55, 2 * BTN_START);
	Macro_Set_Bit(RCC->APB2ENR, 14);

	if(start_en)
	{
		Macro_Write_Block(SYSCFG->EXTICR[0], 0xf, 0x1, BTN_START * 4);
		Macro_Set_Bit(EXTI->FTSR, BTN_START);
		EXTI->PR = (0x1 << BTN_START);
		NVIC_ClearPendingIRQ(BTN_START_IRQN);
		Macro_Set_Bit(EXTI->IMR, BTN_START);
		NVIC_EnableIRQ(BTN_START_IRQN);
	}
	else
	{
		Macro_Clear_Bit(EXTI->IMR, BTN_START);
		NVIC_DisableIRQ(BTN_START_IRQN);
		EXTI->PR = (0x1 << BTN_START);
		NVIC_ClearPendingIRQ(BTN_START_IRQN);
	}

	if(check_en)
	{
		Macro_Write_Block(SYSCFG->EXTICR[0], 0xf, 0x1, BTN_CHECK * 4);
		Macro_Set_Bit(EXTI->FTSR, BTN_CHECK);
		EXTI->PR = (0x1 << BTN_CHECK);
		NVIC_ClearPendingIRQ(BTN_CHECK_IRQN);
		Macro_Set_Bit(EXTI->IMR, BTN_CHECK);
		NVIC_EnableIRQ(BTN_CHECK_IRQN);
	}
	else
	{
		Macro_Clear_Bit(EXTI->IMR, BTN_CHECK);
		NVIC_DisableIRQ(BTN_CHECK_IRQN);
		EXTI->PR = (0x1 << BTN_CHECK);
		NVIC_ClearPendingIRQ(BTN_CHECK_IRQN);
	}

	if(pause_en)
	{
		Macro_Write_Block(SYSCFG->EXTICR[1], 0xf, 0x1, 0);
		Macro_Set_Bit(EXTI->FTSR, BTN_PAUSE);
		EXTI->PR = (0x1 << BTN_PAUSE);
		NVIC_ClearPendingIRQ(BTN_PAUSE_IRQN);
		Macro_Set_Bit(EXTI->IMR, BTN_PAUSE);
		NVIC_EnableIRQ(BTN_PAUSE_IRQN);
	} 
	else
	{
		Macro_Clear_Bit(EXTI->IMR, BTN_PAUSE);
		NVIC_DisableIRQ(BTN_PAUSE_IRQN);
		EXTI->PR = (0x1 << BTN_PAUSE);
		NVIC_ClearPendingIRQ(BTN_PAUSE_IRQN);
	}
		
	if(reset_en)
	{
		Macro_Write_Block(SYSCFG->EXTICR[1], 0xf, 0x1, 4);
		Macro_Set_Bit(EXTI->FTSR, BTN_RESET);
		EXTI->PR = (0x1 << BTN_RESET);
		NVIC_ClearPendingIRQ(BTN_RESET_IRQN);
		Macro_Set_Bit(EXTI->IMR, BTN_RESET);
		NVIC_EnableIRQ(BTN_RESET_IRQN);
	}
	else
	{
		Macro_Clear_Bit(EXTI->IMR, BTN_RESET);
		NVIC_DisableIRQ(BTN_RESET_IRQN);
		EXTI->PR = (0x1 << BTN_RESET);
		NVIC_ClearPendingIRQ(BTN_RESET_IRQN);
	}
}
volatile btn_status_t btn_state = BTN_RELEASED;
volatile uint8_t is_pause = 0;

void EXTI2_IRQHandler(void)
{
	EXTI->PR = (0x1 << BTN_START);
	NVIC_ClearPendingIRQ(BTN_START_IRQN);
	btn_state = BTN_START_PRESSED;
	Btn_ISR_Enable(0, 0, 0, 0);
}

void EXTI3_IRQHandler(void)
{
	EXTI->PR = (0x1 << BTN_CHECK);
	NVIC_ClearPendingIRQ(BTN_CHECK_IRQN);
	btn_state = BTN_CHECK_PRESSED;
	Btn_ISR_Enable(0, 0, 0, 0);
}

void EXTI4_IRQHandler(void)
{
	EXTI->PR = (0x1 << BTN_PAUSE);
	NVIC_ClearPendingIRQ(BTN_PAUSE_IRQN);
	NVIC_DisableIRQ(BTN_PAUSE_IRQN);
	Macro_Clear_Bit(EXTI->IMR, BTN_PAUSE);
	btn_state = BTN_PAUSE_PRESSED;
}

void EXTI9_5_IRQHandler(void)
{
	EXTI->PR = (0x1 << BTN_RESET);
	NVIC_ClearPendingIRQ(BTN_RESET_IRQN);
	Btn_ISR_Enable(0, 0, 0, 0);
	btn_state = BTN_RESET_PRESSED;
}