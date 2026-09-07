#include "buzzer.h"
#include "timer.h"

void Buzzer_Beep(unsigned char tone, int duration)
{
	const static unsigned short tone_value[] = {261,277,293,311,329,349,369,391,415,440,466,493,523,554,587,622,659,698,739,783,830,880,932,987};

	TIM3_Freq_Generation_DR50(tone_value[tone]);
	TIM2_Delay_Interrupt_Enable(1, duration);
	TIM3_Out_Stop();
}

void Wrong_Sound(void)
{
	TIM3_Freq_Generation_DR50(350);
}

void Correct_Sound(uint32_t freq)
{
	TIM3_Freq_Generation_DR50(freq);
}

void Buzzer_Stop(void)
{
	TIM3_Out_Stop();
}

void Buzzer_Delay_ms(int time)
{
	TIM2_Delay_Interrupt_Enable(1, time);
}


#if 0
int i;
	enum key{C1, C1_, D1, D1_, E1, F1, F1_, G1, G1_, A1, A1_, B1, C2, C2_, D2, D2_, E2, F2, F2_, G2, G2_, A2, A2_, B2};
	enum note{N16=BASE/4, N8=BASE/2, N4=BASE, N2=BASE*2, N1=BASE*4};
	const int song1[][2] = {{G1,N4},{G1,N4},{E1,N8},{F1,N8},{G1,N4},{A1,N4},{A1,N4},{G1,N2},{G1,N4},{C2,N4},{E2,N4},{D2,N8},{C2,N8},{D2,N2}};
	const char * note_name[] = {"C1", "C1#", "D1", "D1#", "E1", "F1", "F1#", "G1", "G1#", "A1", "A1#", "B1", "C2", "C2#", "D2", "D2#", "E2", "F2", "F2#", "G2", "G2#", "A2", "A2#", "B2"};

	TIM3_Out_Init();

	while(1)
	{
		for(int i = 0; i < 2; i ++)
		{
			printf("Wrong\n");
			TIM3_Out_PWM_Generation(50, 50);
			TIM2_Delay(100);

			TIM3_Out_PWM_Generation(50, 0);
			TIM2_Delay(100);
		}

		TIM2_Delay(1000);
	}

	
	for(;;);
	printf("Buzeer_Beep Start\n");
	printf("%s ", note_name[C1]);
	Buzzer_Beep(C1,N4);
	printf("%s ", note_name[D1]);
	Buzzer_Beep(D1,N4);
	printf("%s ", note_name[E1]);
	Buzzer_Beep(E1,N4);
	printf("%s ", note_name[F1]);
	Buzzer_Beep(F1,N4);
	printf("%s ", note_name[G1]);
	Buzzer_Beep(G1,N4);
	printf("%s ", note_name[A1]);
	Buzzer_Beep(A1,N4);
	printf("%s ", note_name[B1]);
	Buzzer_Beep(B1,N4);
	printf("%s ", note_name[C2]);
	Buzzer_Beep(C2,N4);

	printf("\nSong Play\n");

	for(i=0; i<(sizeof(song1)/sizeof(song1[0])); i++)
	{
		printf("%s ", note_name[song1[i][0]]);
		Buzzer_Beep(song1[i][0], song1[i][1]);
	}
#endif