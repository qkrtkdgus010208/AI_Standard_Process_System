#ifndef __BUZZER_H__
#define __BUZZER_H__

#include "common.h"
#include <stdint.h>

typedef struct {
	uint16_t freq;     // Hz (0 = 무음 / 간격)
	uint16_t duration; // ms (0 = 시퀀스 종료 마커)
} SoundNote_t;

typedef enum {
	SOUND_NONE = 0,
	SOUND_START,      // 작업 시작 (도 - 미 - 솔)
	SOUND_PASS,       // 중간 STEP 통과 (도 - 솔)
	SOUND_FAIL,       // AI 판정 FAIL (저음 경고 2회)
	SOUND_COMPLETE,   // 모든 STEP 완료 / 작업 정상 종료 (도-미-솔-도 팡파레)
	SOUND_PAUSE,      // 일시정지 (하강 2음: 솔 - 도)
	SOUND_RESUME,     // 작업재개 (상승 2음: 도 - 솔)
	SOUND_DEFECT      // 수동 불량 등록 / 리셋 (저음 3단계 하강 경고)
} SoundId_t;

void Buzzer_Init(void);
void Buzzer_Play(SoundId_t sound_id);
void Buzzer_Stop(void);
void Buzzer_Process_Timer(void);
int Buzzer_Is_Playing(void);

#endif