#include "common.h"

#define BTN_START   2
#define BTN_CHECK   3
#define BTN_PAUSE   4
#define BTN_RESET   5

#define BTN_START_IRQN  8
#define BTN_CHECK_IRQN  9
#define BTN_PAUSE_IRQN  10
#define BTN_RESET_IRQN  23

typedef enum{BTN_RELEASED = 0, BTN_START_PRESSED, BTN_CHECK_PRESSED, BTN_PAUSE_PRESSED, BTN_RESET_PRESSED} btn_status_t;
// Key.c

void Key_Poll_Init(void);
int Key_Get_Pressed(void);
void Key_Wait_Key_Released(void);
void Key_Wait_Key_Pressed(void);
void Btn_ISR_Enable(int start_en, int check_en, int pause_en, int reset_en);
void EXTI2_IRQHandler(void);
void EXTI3_IRQHandler(void);
void EXTI4_IRQHandler(void);
void EXTI9_5_IRQHandler(void);

extern volatile btn_status_t btn_state;
extern volatile uint8_t is_pause;