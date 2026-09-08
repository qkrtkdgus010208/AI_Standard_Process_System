#include "timer.h"
#include "buzzer.h"
#include "led.h"
#include "uart.h"
#include "key.h"

// SysTick.c

extern void SysTick_Run(unsigned int msec);
extern int SysTick_Check_Timeout(void);
extern unsigned int SysTick_Get_Time(void);
extern unsigned int SysTick_Get_Load_Time(void);
extern void SysTick_Stop(void);

// Clock.c

extern void Clock_Init(void);