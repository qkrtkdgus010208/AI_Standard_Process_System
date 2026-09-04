#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include "common.h"
#include "malloc.h"

void Uart2_Init(int baud);
void Uart2_Send_Byte(char data);
void Uart2_Send_String(const char *pt);
void UART2_RX_Interrupt_Enable(int en);
void USART2_IRQHandler(void);
void Uart1_Init(int baud);
void Uart1_Send_Byte(char data);
void Uart1_Send_String(char *pt);
void Uart1_Printf(char *fmt,...);
char Uart1_Get_Char(void);
char Uart1_Get_Pressed(void);
char Uart2_Get_Pressed(void);