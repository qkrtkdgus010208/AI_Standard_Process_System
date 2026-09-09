#include "buzzer.h"
#include "timer.h"
#include "key.h"
#include "led.h"

extern volatile led_step_t led_step;
extern volatile uint8_t is_pause;

static const SoundNote_t Notes_Start[] = {
	{523, 100},
	{0, 30},
	{659, 100},
	{0, 30},
	{784, 180},
	{0, 0}
};

static const SoundNote_t Notes_Pass[] = {
	{1047, 120},
	{0, 50},
	{784, 180},
	{0, 0}
};

static const SoundNote_t Notes_Fail[] = {
	{350, 220},
	{0, 80},
	{350, 220},
	{0, 0}
};

static const SoundNote_t Notes_Complete[] = {
	{523, 100},
	{659, 100},
	{784, 100},
	{1047, 320},
	{0, 0}
};

static const SoundNote_t Notes_Pause[] = {
	{784, 80},
	{0, 30},
	{523, 130},
	{0, 0}
};

static const SoundNote_t Notes_Resume[] = {
	{523, 80},
	{0, 30},
	{784, 130},
	{0, 0}
};

static const SoundNote_t Notes_Defect[] = {
	{440, 100},
	{0, 40},
	{330, 100},
	{0, 40},
	{220, 260},
	{0, 0}
};

static const SoundNote_t *Current_Seq = 0;
static uint8_t Seq_Idx = 0;
static volatile uint8_t Is_Playing = 0;
static uint8_t Lock_Buttons = 0;

void Buzzer_Init(void)
{
	TIM3_Out_Init();
	Is_Playing = 0;
	Current_Seq = 0;
	Seq_Idx = 0;
}

void Buzzer_Stop(void)
{
	TIM3_Out_Stop();
	TIM2_Delay_Interrupt_Enable(0, 0);
	Is_Playing = 0;
	Current_Seq = 0;
	Seq_Idx = 0;
}

int Buzzer_Is_Playing(void)
{
	return Is_Playing;
}

void Buzzer_Play(SoundId_t sound_id)
{
	switch (sound_id)
	{
	case SOUND_START:
		Current_Seq = Notes_Start;
		Lock_Buttons = 1;
		break;
	case SOUND_PASS:
		Current_Seq = Notes_Pass;
		Lock_Buttons = 1;
		break;
	case SOUND_FAIL:
		Current_Seq = Notes_Fail;
		Lock_Buttons = 1;
		break;
	case SOUND_COMPLETE:
		Current_Seq = Notes_Complete;
		Lock_Buttons = 1;
		break;
	case SOUND_PAUSE:
		Current_Seq = Notes_Pause;
		Lock_Buttons = 0;
		break;
	case SOUND_RESUME:
		Current_Seq = Notes_Resume;
		Lock_Buttons = 0;
		break;
	case SOUND_DEFECT:
		Current_Seq = Notes_Defect;
		Lock_Buttons = 1;
		break;
	default:
		Buzzer_Stop();
		return;
	}

	TIM3_Out_Stop();
	TIM2_Delay_Interrupt_Enable(0, 0);

	Seq_Idx = 0;
	Is_Playing = 1;

	if (Lock_Buttons)
	{
		Btn_ISR_Enable(0, 0, 0, 0);
	}

	if (Current_Seq[0].freq > 0)
	{
		TIM3_Freq_Generation_DR50(Current_Seq[0].freq);
	}
	else
	{
		TIM3_Out_Stop();
	}
	TIM2_Delay_Interrupt_Enable(1, Current_Seq[0].duration);
}

void Buzzer_Process_Timer(void)
{
	if (!Is_Playing || Current_Seq == 0)
		return;

	Seq_Idx++;
	if (Current_Seq[Seq_Idx].duration == 0)
	{
		Buzzer_Stop();
		if (Lock_Buttons)
		{
			if (led_step == LED_STEP0)
			{
				Btn_ISR_Enable(1, 0, 0, 0);
			}
			else
			{
				Btn_ISR_Enable(0, !is_pause, 1, !is_pause);
			}
		}
		return;
	}

	if (Current_Seq[Seq_Idx].freq > 0)
	{
		TIM3_Freq_Generation_DR50(Current_Seq[Seq_Idx].freq);
	}
	else
	{
		TIM3_Out_Stop();
	}
	TIM2_Delay_Interrupt_Enable(1, Current_Seq[Seq_Idx].duration);
}