#ifndef _TIMER_H_
#define _TIMER_H_

#include "common.h"

#define TIM2_TICK         	(20) 				// usec
#define TIM2_FREQ 	  		(1000000./TIM2_TICK)	// Hz
#define TIME2_PLS_OF_1ms  	(TIM2_FREQ / 1000.)
#define TIM2_MAX	  		(0xffffffffu)

#define TIM3_FREQ					(800000.)			// Hz
#define TIM3_TICK					(1000000/TIM3_FREQ)	// usec
#define TIME3_PLS_OF_1ms			(1000/TIM3_TICK)

void TIM2_Delay_Interrupt_Enable(int en, int time);
void TIM3_Out_Init(void);
void TIM3_Freq_Generation_DR50(unsigned short freq);
void TIM3_Out_Stop(void);

#endif /* _TIMER_H_ */