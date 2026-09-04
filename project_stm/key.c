#include "key.h"

void Key_Poll_Init(void)
{
	Macro_Set_Bit(RCC->AHB1ENR, 2); 
	Macro_Write_Block(GPIOC->MODER, 0x3, 0x0, 26);
}

int Key_Get_Pressed(void)
{
	return Macro_Check_Bit_Clear(GPIOC->IDR, 13);	
}

void Key_Wait_Key_Pressed(void)
{
	while(!Macro_Check_Bit_Clear(GPIOC->IDR, 13));
}

void Key_Wait_Key_Released(void)
{
	while(!Macro_Check_Bit_Set(GPIOC->IDR, 13));
}

void Btn_ISR_Enable(int check_en, int pause_en, int reset_en)
{
	if(check_en && pause_en && reset_en)
	{
		Macro_Set_Bit(RCC->AHB1ENR, 1);
		Macro_Write_Block(GPIOB->MODER, 0x3f, 0x00, 2 * BTN_CHECK);
		Macro_Write_Block(GPIOB->PUPDR, 0x3f, 0x15, 2 * BTN_CHECK);

		Macro_Set_Bit(RCC->APB2ENR, 14);
	}

	if(check_en)
	{
		Macro_Write_Block(SYSCFG->EXTICR[0], 0xf, 0x1, 3 * 4);
		Macro_Set_Bit(EXTI->FTSR, BTN_CHECK);
		Macro_Set_Bit(EXTI->PR, BTN_CHECK);
		NVIC_ClearPendingIRQ(BTN_CHECK_IRQN);
		Macro_Set_Bit(EXTI->IMR, BTN_CHECK);
		NVIC_EnableIRQ(BTN_CHECK_IRQN);

	}

	else
		NVIC_DisableIRQ(BTN_CHECK_IRQN);

	if(pause_en)
	{
		Macro_Write_Block(SYSCFG->EXTICR[1], 0xf, 0x1, 0);
		Macro_Set_Bit(EXTI->FTSR, BTN_PAUSE);
		Macro_Set_Bit(EXTI->PR, BTN_PAUSE);
		NVIC_ClearPendingIRQ(BTN_PAUSE_IRQN);
		Macro_Set_Bit(EXTI->IMR, BTN_PAUSE);
		NVIC_EnableIRQ(BTN_PAUSE_IRQN);
		

	} 

	else
		NVIC_DisableIRQ(BTN_PAUSE_IRQN);
		//PB3, 4,5가 EXTI 소스가 되도록 설정
		
	if(reset_en)
	{
		Macro_Write_Block(SYSCFG->EXTICR[1], 0xf, 0x1, 4);
		Macro_Set_Bit(EXTI->FTSR, BTN_RESET);
		Macro_Set_Bit(EXTI->PR, BTN_RESET);
		NVIC_ClearPendingIRQ(BTN_RESET_IRQN);
		Macro_Set_Bit(EXTI->IMR, BTN_RESET);
		NVIC_EnableIRQ(BTN_RESET_IRQN);
	}

	else
		NVIC_DisableIRQ(BTN_RESET_IRQN);
}
volatile btn_status_t btn_state = BTN_RELEASED;
volatile uint8_t is_pause= 0;

void EXTI3_IRQHandler(void)
{
	btn_state = BTN_CHECK_PRESSED;
	EXTI->PR |= (0x1 << BTN_CHECK);
	NVIC_ClearPendingIRQ(BTN_CHECK_IRQN);
	Btn_ISR_Enable(0, 0, 0);
}
void EXTI4_IRQHandler(void)
{
	btn_state = BTN_PAUSE_PRESSED;
	EXTI->PR |= (0x1 << BTN_PAUSE);
	NVIC_ClearPendingIRQ(BTN_PAUSE_IRQN);
	is_pause ^= 1;
}
void EXTI9_5_IRQHandler(void)
{
	btn_state = BTN_RESET_PRESSED;
	EXTI->PR |= (0x1 << BTN_RESET);
	NVIC_ClearPendingIRQ(BTN_RESET_IRQN);
}