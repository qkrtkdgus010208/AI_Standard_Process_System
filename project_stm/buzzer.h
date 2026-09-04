#include "common.h"
#include "malloc.h"

#define BASE  (500) //msec
#define WRONG_ON_TIME_MS       200
#define WRONG_OFF_TIME_MS      200
#define WRONG_REPEAT_COUNT     3




void Buzzer_Beep(unsigned char tone, int duration);
void Wrong_Sound(void);
void Correct_Sound(uint32_t freq);
void Buzzer_Stop(void);
void Buzzer_Delay_ms(int time);