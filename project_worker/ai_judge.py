"""AI Framework와 PyQt UI 사이의 의존성을 분리하는 판정 모듈입니다."""

import random
import threading
import time
from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

import config


@dataclass(frozen=True)
class JudgeResult:
    """AI Backend 종류와 무관하게 UI에 전달되는 표준 판정 결과입니다."""

    result: str
    confidence: float
    detail: str = ""


class BaseJudge:
    """PyTorch, TensorRT 등 실제 판정 구현체가 따라야 할 인터페이스입니다."""

    def predict(self, frame) -> JudgeResult:
        raise NotImplementedError


class MockJudge(BaseJudge):
    """장비와 모델 없이 PASS/FAIL 흐름을 시험하는 Mock 판정기입니다."""

    def predict(self, frame) -> JudgeResult:
        time.sleep(0.18)  # 느린 실제 추론 상황을 가볍게 모사합니다.
        is_pass = random.random() >= 0.25
        confidence = random.uniform(0.88, 0.99)
        result = "PASS" if is_pass else "FAIL"
        return JudgeResult(result, confidence, f"Mock AI 판정: {result}")


def create_judge(backend: Optional[str] = None) -> BaseJudge:
    """설정값에 따라 AI 구현체를 생성합니다."""
    selected = (backend or config.AI_BACKEND).lower()
    if selected == "mock":
        return MockJudge()
    if selected == "pytorch":
        raise NotImplementedError("PyTorchJudge 구현체를 ai_judge.py에 연결하세요.")
    if selected == "tensorrt":
        raise NotImplementedError("TensorRTJudge 구현체를 ai_judge.py에 연결하세요.")
    raise ValueError(f"지원하지 않는 AI Backend: {selected}")


class AiInferenceThread(QThread):
    """최신 Camera Frame을 받아 UI를 막지 않고 AI 추론을 수행합니다."""

    judgement_ready = pyqtSignal(object)
    status_changed = pyqtSignal(str, bool)

    def __init__(self, judge: Optional[BaseJudge] = None, parent=None):
        super().__init__(parent)
        self.judge = judge or create_judge()
        self._condition = threading.Condition()
        self._latest_frame = None
        self._running = False

    def submit_frame(self, frame) -> None:
        """대기열을 늘리지 않고 가장 최신 Frame 하나만 보관합니다."""
        with self._condition:
            self._latest_frame = frame
            self._condition.notify()

    def run(self) -> None:
        """Frame 요청이 들어올 때만 추론을 실행합니다."""
        self._running = True
        self.status_changed.emit("AI 판정 준비", True)
        while self._running:
            with self._condition:
                while self._running and self._latest_frame is None:
                    self._condition.wait(timeout=0.5)
                if not self._running:
                    break
                frame = self._latest_frame
                self._latest_frame = None
            try:
                self.judgement_ready.emit(self.judge.predict(frame))
            except Exception as error:
                self.status_changed.emit(f"AI 추론 오류: {error}", False)

    def stop(self) -> None:
        """추론 Thread를 안전하게 종료합니다."""
        self._running = False
        with self._condition:
            self._condition.notify_all()
        self.wait(3000)
