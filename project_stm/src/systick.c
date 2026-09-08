#include "device_driver.h"

void SysTick_Run(unsigned int msec)
{
	SysTick->CTRL = (0<<2)+(0<<1)+(0<<0);
	SysTick->LOAD = (unsigned int)((HCLK/(8.*1000.))*msec+0.5);
	SysTick->VAL = 0;
	Macro_Set_Bit(SysTick->CTRL, 0);
}

int SysTick_Check_Timeout(void)
{
	return ((SysTick->CTRL >> 16) & 0x1);
}

unsigned int SysTick_Get_Time(void)
{
	return SysTick->VAL;
}

unsigned int SysTick_Get_Load_Time(void)
{
	return SysTick->LOAD;
}

void SysTick_Stop(void)
{
	SysTick->CTRL = 0<<0;
}
