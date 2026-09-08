#include "common.h"
#include "malloc.h"

#define LED_FAIL        9

typedef enum {LED_STEP0 = 0, LED_STEP1 = 1, LED_STEP2, LED_STEP3, LED_STEP4, LED_STEP5, LED_STEP6, LED_STEP7, LED_STEP8, LED_STEP9} led_step_t;

void LED_Init(void);
void LED_On(void);
void LED_Off(void);
void Step_LED_On(uint8_t step);
void Step_LED_Off(uint8_t step);
void Fail_LED_On(void);
void Fail_LED_Off(void);