	.syntax unified
  	.cpu cortex-m4
  	.fpu softvfp	
	.thumb
	.text

	.word	0x20020000
	.word	__start
	.word   NMI_Handler                       @ NMI Handler
	.word   HardFault_Handler                 @ Hard Fault Handler
	.word   MemManage_Handler                 @ MPU Fault Handler
	.word   BusFault_Handler                  @ Bus Fault Handler
	.word   UsageFault_Handler                @ Usage Fault Handler
	.word   Invalid_ISR                       @ Reserved
	.word   Invalid_ISR                       @ Reserved
	.word   Invalid_ISR                       @ Reserved
	.word   Invalid_ISR                       @ Reserved
	.word   SVC_Handler                       @ SVCall Handler
	.word   DebugMon_Handler                  @ Debug Monitor Handler
	.word   Invalid_ISR                       @ Reserved
	.word   PendSV_Handler                    @ PendSV Handler
	.word   SysTick_Handler                   @ SysTick Handler

	@ External Interrupts
	.word   WWDG_IRQHandler                   @ Window WatchDog                                        
	.word   PVD_IRQHandler                    @ PVD through EXTI Line detection                        
	.word   TAMP_STAMP_IRQHandler             @ Tamper and TimeStamps through the EXTI line            
	.word   RTC_WKUP_IRQHandler               @ RTC Wakeup through the EXTI line                       
	.word   FLASH_IRQHandler                  @ FLASH                                           
	.word   RCC_IRQHandler                    @ RCC                                             
	.word   EXTI0_IRQHandler                  @ EXTI Line0                                             
	.word   EXTI1_IRQHandler                  @ EXTI Line1                                             
	.word   EXTI2_IRQHandler                  @ EXTI Line2                                             
	.word   EXTI3_IRQHandler                  @ EXTI Line3                                             
	.word   EXTI4_IRQHandler                  @ EXTI Line4                                             
	.word   DMA1_Stream0_IRQHandler           @ DMA1 Stream 0                                   
	.word   DMA1_Stream1_IRQHandler           @ DMA1 Stream 1                                   
	.word   DMA1_Stream2_IRQHandler           @ DMA1 Stream 2                                   
	.word   DMA1_Stream3_IRQHandler           @ DMA1 Stream 3                                   
	.word   DMA1_Stream4_IRQHandler           @ DMA1 Stream 4                                   
	.word   DMA1_Stream5_IRQHandler           @ DMA1 Stream 5                                   
	.word   DMA1_Stream6_IRQHandler           @ DMA1 Stream 6                                   
	.word   ADC_IRQHandler                    @ ADC1, ADC2 and ADC3s                            
	.word   Invalid_ISR                       @ Reserved                     
	.word   Invalid_ISR                       @ Reserved                    
	.word   Invalid_ISR                       @ Reserved                  
	.word   Invalid_ISR                       @ Reserved                    
	.word   EXTI9_5_IRQHandler                @ External Line[9:5]s                                    
	.word   TIM1_BRK_TIM9_IRQHandler          @ TIM1 Break and TIM9                   
	.word   TIM1_UP_TIM10_IRQHandler          @ TIM1 Update and TIM10                 
	.word   TIM1_TRG_COM_TIM11_IRQHandler     @ TIM1 Trigger and Commutation and TIM11
	.word   TIM1_CC_IRQHandler                @ TIM1 Capture Compare                                   
	.word   TIM2_IRQHandler                   @ TIM2                                            
	.word   TIM3_IRQHandler                   @ TIM3                                            
	.word   TIM4_IRQHandler                   @ TIM4                                            
	.word   I2C1_EV_IRQHandler                @ I2C1 Event                                             
	.word   I2C1_ER_IRQHandler                @ I2C1 Error                                             
	.word   I2C2_EV_IRQHandler                @ I2C2 Event                                             
	.word   I2C2_ER_IRQHandler                @ I2C2 Error                                               
	.word   SPI1_IRQHandler                   @ SPI1                                            
	.word   SPI2_IRQHandler                   @ SPI2                                            
	.word   USART1_IRQHandler                 @ USART1                                          
	.word   USART2_IRQHandler                 @ USART2                                          
	.word   Invalid_ISR                       @ Reserved               
	.word   EXTI15_10_IRQHandler              @ External Line[15:10]s                                  
	.word   RTC_Alarm_IRQHandler              @ RTC Alarm (A and B) through EXTI Line                  
	.word   OTG_FS_WKUP_IRQHandler            @ USB OTG FS Wakeup through EXTI line                        
	.word   Invalid_ISR                       @ Reserved                  
	.word   Invalid_ISR                       @ Reserved                 
	.word   Invalid_ISR                       @ Reserved
	.word   Invalid_ISR                       @ Reserved        
	.word   DMA1_Stream7_IRQHandler           @ DMA1 Stream7                                           
	.word   Invalid_ISR                       @ Reserved                  
	.word   SDIO_IRQHandler                   @ SDIO                                            
	.word   TIM5_IRQHandler                   @ TIM5                                            
	.word   SPI3_IRQHandler                   @ SPI3                                            
	.word   Invalid_ISR                       @ Reserved                
	.word   Invalid_ISR                       @ Reserved                
	.word   Invalid_ISR                       @ Reserved                   
	.word   Invalid_ISR                       @ Reserved                   
	.word   DMA2_Stream0_IRQHandler           @ DMA2 Stream 0                                   
	.word   DMA2_Stream1_IRQHandler           @ DMA2 Stream 1                                   
	.word   DMA2_Stream2_IRQHandler           @ DMA2 Stream 2                                   
	.word   DMA2_Stream3_IRQHandler           @ DMA2 Stream 3                                   
	.word   DMA2_Stream4_IRQHandler           @ DMA2 Stream 4
	.word   Invalid_ISR                       @ Reserved  
	.word   Invalid_ISR                       @ Reserved  
	.word   Invalid_ISR                       @ Reserved                   
	.word   Invalid_ISR                       @ Reserved                    
	.word   Invalid_ISR                       @ Reserved                    
	.word   Invalid_ISR                       @ Reserved                    
	.word   OTG_FS_IRQHandler                 @ USB OTG FS                                      
	.word   DMA2_Stream5_IRQHandler           @ DMA2 Stream 5                                   
	.word   DMA2_Stream6_IRQHandler           @ DMA2 Stream 6                                   
	.word   DMA2_Stream7_IRQHandler           @ DMA2 Stream 7                                   
	.word   USART6_IRQHandler                 @ USART6                                           
	.word   I2C3_EV_IRQHandler                @ I2C3 event                                             
	.word   I2C3_ER_IRQHandler                @ I2C3 error                                             
	.word   Invalid_ISR                       @ Reserved                     
	.word   Invalid_ISR                       @ Reserved 
	.word   Invalid_ISR                       @ Reserved   
	.word   Invalid_ISR                       @ Reserved         
	.word   Invalid_ISR                       @ Reserved  
	.word   Invalid_ISR                       @ Reserved                                      
	.word   Invalid_ISR                       @ Reserved
	.word   FPU_IRQHandler                    @ FPU
	.word   Invalid_ISR                       @ Reserved
	.word   Invalid_ISR                       @ Reserved
	.word   SPI4_IRQHandler                   @ SPI4
	.word   SPI5_IRQHandler                   @ SPI5

    .weak   NMI_Handler
    .thumb_set _Invalid_ISR, Invalid_ISR

    .weak   Invalid_ISR
  	.type 	Invalid_ISR, %function
Invalid_ISR:	
	B		_Invalid_ISR

    .weak   NMI_Handler
    .thumb_set NMI_Handler, Invalid_ISR

    .weak   HardFault_Handler
    .thumb_set HardFault_Handler, Invalid_ISR

    .weak   MemManage_Handler
    .thumb_set MemManage_Handler, Invalid_ISR

    .weak   BusFault_Handler
    .thumb_set BusFault_Handler, Invalid_ISR

    .weak   UsageFault_Handler
    .thumb_set UsageFault_Handler, Invalid_ISR

    .weak   SVC_Handler
    .thumb_set SVC_Handler, Invalid_ISR

    .weak   DebugMon_Handler
    .thumb_set DebugMon_Handler, Invalid_ISR

    .weak   PendSV_Handler
    .thumb_set PendSV_Handler, Invalid_ISR

    .weak   SysTick_Handler
    .thumb_set SysTick_Handler, Invalid_ISR

    .weak   WWDG_IRQHandler
    .thumb_set WWDG_IRQHandler, Invalid_ISR

    .weak   PVD_IRQHandler
    .thumb_set PVD_IRQHandler, Invalid_ISR

    .weak   TAMP_STAMP_IRQHandler
    .thumb_set TAMP_STAMP_IRQHandler, Invalid_ISR

    .weak   RTC_WKUP_IRQHandler
    .thumb_set RTC_WKUP_IRQHandler, Invalid_ISR

    .weak   FLASH_IRQHandler
    .thumb_set FLASH_IRQHandler, Invalid_ISR

    .weak   RCC_IRQHandler
    .thumb_set RCC_IRQHandler, Invalid_ISR

    .weak   EXTI0_IRQHandler
    .thumb_set EXTI0_IRQHandler, Invalid_ISR

    .weak   EXTI1_IRQHandler
    .thumb_set EXTI1_IRQHandler, Invalid_ISR

    .weak   EXTI2_IRQHandler
    .thumb_set EXTI2_IRQHandler, Invalid_ISR

    .weak   EXTI3_IRQHandler
    .thumb_set EXTI3_IRQHandler, Invalid_ISR

    .weak   EXTI4_IRQHandler
    .thumb_set EXTI4_IRQHandler, Invalid_ISR

    .weak   DMA1_Stream0_IRQHandler
    .thumb_set DMA1_Stream0_IRQHandler, Invalid_ISR

    .weak   DMA1_Stream1_IRQHandler
    .thumb_set DMA1_Stream1_IRQHandler, Invalid_ISR

    .weak   DMA1_Stream2_IRQHandler
    .thumb_set DMA1_Stream2_IRQHandler, Invalid_ISR

    .weak   DMA1_Stream3_IRQHandler
    .thumb_set DMA1_Stream3_IRQHandler, Invalid_ISR

    .weak   DMA1_Stream4_IRQHandler
    .thumb_set DMA1_Stream4_IRQHandler, Invalid_ISR

    .weak   DMA1_Stream5_IRQHandler
    .thumb_set DMA1_Stream5_IRQHandler, Invalid_ISR

    .weak   DMA1_Stream6_IRQHandler
    .thumb_set DMA1_Stream6_IRQHandler, Invalid_ISR

    .weak   ADC_IRQHandler
    .thumb_set ADC_IRQHandler, Invalid_ISR

    .weak   EXTI9_5_IRQHandler
    .thumb_set EXTI9_5_IRQHandler, Invalid_ISR

    .weak   TIM1_BRK_TIM9_IRQHandler
    .thumb_set TIM1_BRK_TIM9_IRQHandler, Invalid_ISR

    .weak   TIM1_UP_TIM10_IRQHandler
    .thumb_set TIM1_UP_TIM10_IRQHandler, Invalid_ISR

    .weak   TIM1_TRG_COM_TIM11_IRQHandler
    .thumb_set TIM1_TRG_COM_TIM11_IRQHandler, Invalid_ISR

    .weak   TIM1_CC_IRQHandler
    .thumb_set TIM1_CC_IRQHandler, Invalid_ISR

    .weak   TIM2_IRQHandler
    .thumb_set TIM2_IRQHandler, Invalid_ISR

    .weak   TIM3_IRQHandler
    .thumb_set TIM3_IRQHandler, Invalid_ISR

    .weak   TIM4_IRQHandler
    .thumb_set TIM4_IRQHandler, Invalid_ISR

    .weak   I2C1_EV_IRQHandler
    .thumb_set I2C1_EV_IRQHandler, Invalid_ISR

    .weak   I2C1_ER_IRQHandler
    .thumb_set I2C1_ER_IRQHandler, Invalid_ISR

    .weak   I2C2_EV_IRQHandler
    .thumb_set I2C2_EV_IRQHandler, Invalid_ISR

    .weak   I2C2_ER_IRQHandler
    .thumb_set I2C2_ER_IRQHandler, Invalid_ISR

    .weak   SPI1_IRQHandler
    .thumb_set SPI1_IRQHandler, Invalid_ISR

    .weak   SPI2_IRQHandler
    .thumb_set SPI2_IRQHandler, Invalid_ISR

    .weak   USART1_IRQHandler
    .thumb_set USART1_IRQHandler, Invalid_ISR

    .weak   USART2_IRQHandler
    .thumb_set USART2_IRQHandler, Invalid_ISR

    .weak   EXTI15_10_IRQHandler
    .thumb_set EXTI15_10_IRQHandler, Invalid_ISR

    .weak   RTC_Alarm_IRQHandler
    .thumb_set RTC_Alarm_IRQHandler, Invalid_ISR

    .weak   OTG_FS_WKUP_IRQHandler
    .thumb_set OTG_FS_WKUP_IRQHandler, Invalid_ISR

    .weak   DMA1_Stream7_IRQHandler
    .thumb_set DMA1_Stream7_IRQHandler, Invalid_ISR

    .weak   SDIO_IRQHandler
    .thumb_set SDIO_IRQHandler, Invalid_ISR

    .weak   TIM5_IRQHandler
    .thumb_set TIM5_IRQHandler, Invalid_ISR

    .weak   SPI3_IRQHandler
    .thumb_set SPI3_IRQHandler, Invalid_ISR

    .weak   DMA2_Stream0_IRQHandler
    .thumb_set DMA2_Stream0_IRQHandler, Invalid_ISR

    .weak   DMA2_Stream1_IRQHandler
    .thumb_set DMA2_Stream1_IRQHandler, Invalid_ISR

    .weak   DMA2_Stream2_IRQHandler
    .thumb_set DMA2_Stream2_IRQHandler, Invalid_ISR

    .weak   DMA2_Stream3_IRQHandler
    .thumb_set DMA2_Stream3_IRQHandler, Invalid_ISR

    .weak   DMA2_Stream4_IRQHandler
    .thumb_set DMA2_Stream4_IRQHandler, Invalid_ISR

    .weak   OTG_FS_IRQHandler
    .thumb_set OTG_FS_IRQHandler, Invalid_ISR

    .weak   DMA2_Stream5_IRQHandler
    .thumb_set DMA2_Stream5_IRQHandler, Invalid_ISR

    .weak   DMA2_Stream6_IRQHandler
    .thumb_set DMA2_Stream6_IRQHandler, Invalid_ISR

    .weak   DMA2_Stream7_IRQHandler
    .thumb_set DMA2_Stream7_IRQHandler, Invalid_ISR

    .weak   USART6_IRQHandler
    .thumb_set USART6_IRQHandler, Invalid_ISR

    .weak   I2C3_EV_IRQHandler
    .thumb_set I2C3_EV_IRQHandler, Invalid_ISR

    .weak   I2C3_ER_IRQHandler
    .thumb_set I2C3_ER_IRQHandler, Invalid_ISR

    .weak   FPU_IRQHandler
    .thumb_set FPU_IRQHandler, Invalid_ISR

    .weak   SPI4_IRQHandler
    .thumb_set SPI4_IRQHandler, Invalid_ISR

    .weak   SPI5_IRQHandler
    .thumb_set SPI5_IRQHandler, Invalid_ISR

	.global	__start
  	.type 	__start, %function
__start:

	.equ GPIOA_LCKR,	0x4002001C @ Lock PA[14:13] for ST-LINK
	.equ RCC_AHB1ENR,  	0x40023830 @ PA : [0] = 1, PC : [2] = 1

	@ GPIOA, GPIOC clock on
	LDR   	r0, =RCC_AHB1ENR
	LDR   	r1, [r0]
	ORR	  	r1, r1, #(0x1<<2)|(0x1<<0)
	STR   	r1, [r0]

	@ Lock PA[14:13] pin configuration for ST-LINK
	LDR		r0, =GPIOA_LCKR
	LDR		r1, =(0x1<<16)|(0x3<<13)
	STR		r1, [r0]
	LDR		r1, =(0x0<<16)|(0x3<<13)
	STR		r1, [r0]
	LDR		r1, =(0x1<<16)|(0x3<<13)
	STR		r1, [r0]
	LDR		r1, [r0]

	@ CRT Startup Code

	.extern __RO_LIMIT__
	.extern __RW_BASE__
	.extern __ZI_BASE__
	.extern __ZI_LIMIT__

	LDR		r0, =__RO_LIMIT__
	LDR		r1, =__RW_BASE__
	LDR		r3, =__ZI_BASE__

	CMP		r0, r1
	BEQ		2f

1:
	CMP		r1, r3
	ITT		LO
	LDRLO	r2, [r0], #4
	STRLO	r2, [r1], #4
	BLO		1b

2:
	LDR		r1, =__ZI_LIMIT__
	MOV		r2, #0x0
3:
	CMP		r3, r1
	ITT		lo
	STRLO	r2, [r3], #4
	BLO		3b

	.extern Main

	BL		Main

	B		.
			
	.end
