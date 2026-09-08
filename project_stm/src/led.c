#include "led.h"

void LED_Init(void)
{
	/* 아래 코드 수정 금지 : Port-A Clock Enable */
	Macro_Set_Bit(RCC->AHB1ENR, 0);
	// GPIOC Clock Enable
	Macro_Set_Bit(RCC->AHB1ENR, 2);

	// LED를 출력으로 설정하고 초기 OFF
	Macro_Write_Block(GPIOA->MODER, 0x3, 0x1, 10);
	Macro_Clear_Bit(GPIOA->OTYPER, 5);
	Macro_Clear_Bit(GPIOA->ODR, 5);

	// S/F LED 초기화
	Macro_Write_Block(GPIOC->MODER, 0xfffff, 0x55555, 0);
	Macro_Clear_Area(GPIOC->OTYPER, 0x3ff, 0);
	Macro_Clear_Area(GPIOC->ODR, 0x3ff, 0); 
}

void LED_On(void)
{
	// LED On
	Macro_Set_Bit(GPIOA->ODR, 5); 
}

void LED_Off(void)
{
	// LED Off
	Macro_Clear_Bit(GPIOA->ODR, 5); 
}

void Step_LED_On(uint8_t step)
{
	Macro_Set_Bit(GPIOC->ODR, (step - 1));
}

void Step_LED_Off(uint8_t step)
{
	Macro_Clear_Bit(GPIOC->ODR, (step - 1));
}

void Fail_LED_On(void)
{
	Macro_Set_Bit(GPIOC->ODR, LED_FAIL);
}

void Fail_LED_Off(void)
{
	Macro_Clear_Bit(GPIOC->ODR, LED_FAIL);
}