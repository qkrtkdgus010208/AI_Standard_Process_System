#include "common.h"
#include "malloc.h"

#define TIM2_TICK         	(20) 				// usec
#define TIM2_FREQ 	  		(1000000./TIM2_TICK)	// Hz
#define TIME2_PLS_OF_1ms  	(TIM2_FREQ / 1000.)
#define TIM2_MAX	  		(0xffffffffu)

#define TIM3_FREQ					(800000.)			// Hz
#define TIM3_TICK					(1000000/TIM3_FREQ)	// usec
#define TIME3_PLS_OF_1ms			(1000/TIM3_TICK)

#if 0
// #define TIM3_TARGET_FREQ	(8000000)			// Hz
// #define TIM3_TICK			(1000000. / TIM3_TARGET_FREQ)	// usec
// #define TIME3_PLS_OF_1ms	(TIM3_TARGET_FREQ / 1000.)

// #define TIM4_TICK	  		(20) 				// usec
// #define TIM4_FREQ 	  		(1000000/TIM4_TICK) // Hz
// #define TIME4_PLS_OF_1ms  	(1000/TIM4_TICK)
// #define TIM4_MAX	  		(0xffffu)
#endif

void TIM2_Delay_Interrupt_Enable(int en, int time);
void TIM3_Out_Init(void);
void TIM3_Freq_Generation_DR50(unsigned short freq);
void TIM3_Out_Stop(void);


#if 0
void TIM2_Delay(int time);
extern void TIM2_Stopwatch_Start(void);
extern unsigned int TIM2_Stopwatch_Stop(void);

extern int TIM4_Check_Timeout(void);
extern void TIM4_Stop(void);
extern void TIM4_Change_Value(int time);
void TIM4_Repeat(int time);

void TIM3_Out_Freq_Generation(unsigned short freq);

void TIM3_Out_PWM_Generation(unsigned short freq, int duty);
#endif