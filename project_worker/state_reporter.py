"""작업 상태 이벤트를 Monitoring PC에 비동기 전송하는 모듈입니다.

큐(Queue) 기반으로 상태 변경 이벤트를 순서대로 서버에 전송하고,
서버에서 복원된 이전 작업 상태를 정규화하는 기능을 제공합니다.
"""

import queue
from typing import Any, Optional

from PyQt5.QtCore import QThread, pyqtSignal

from network_client import send_json_request


def _extract_int(raw: dict, keys: tuple) -> Optional[int]:
    """dict에서 여러 키를 순서대로 탐색하여 정수값을 반환합니다."""
    for k in keys:
        if k in raw:
            try:
                return int(raw[k])
            except (ValueError, TypeError):
                pass
    return None


def parse_work_state_data(raw: Any) -> Optional[dict]:
    """서버 응답에서 이전 작업 상태 데이터를 정규화하여 추출합니다."""
    if not isinstance(raw, dict):
        return None

    # 중첩 구조 평탄화
    raw = raw.get("work_state") or raw.get("state_data") or raw
    if not isinstance(raw, dict):
        return None

    product_id = str(
        raw.get("product_id") or raw.get("productId")
        or raw.get("code") or raw.get("product_code") or ""
    ).strip()
    if not product_id:
        return None

    product_name = str(
        raw.get("product_name") or raw.get("productName")
        or raw.get("name") or raw.get("item_name") or product_id
    ).strip()

    total_steps = max(1, _extract_int(
        raw, ("total_steps", "totalSteps", "steps", "step_count", "process_count")
    ) or 1)

    current_step = _extract_int(
        raw, ("current_step", "currentStep", "step", "step_no")
    ) or 0

    state = str(raw.get("state") or raw.get("status") or "running").strip().lower()
    last_result = str(raw.get("last_result") or raw.get("lastResult") or "waiting").strip().lower()
    defect_type = str(raw.get("defect_type") or raw.get("defectType") or "").strip()
    detail = str(raw.get("detail") or "").strip()

    # 복원 불필요한 상태 필터
    if state == "complete" or (current_step == 0 and state == "idle"):
        return None

    current_step = max(1, min(total_steps, current_step))
    if state not in ("running", "paused"):
        state = "running"

    return {
        "product_id": product_id,
        "product_name": product_name,
        "total_steps": total_steps,
        "current_step": current_step,
        "state": state,
        "last_result": last_result,
        "defect_type": defect_type,
        "detail": detail,
    }


class MonitoringEventThread(QThread):
    """인증 Session Token으로 작업상태를 비동기 전송합니다."""

    status_changed = pyqtSignal(str, bool)

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self._queue: queue.Queue = queue.Queue()
        self._running = False

    def enqueue_state(self, state: dict) -> None:
        """현재 Session 소유자의 상태를 Queue에 넣습니다."""
        self._queue.put({
            "type": "state",
            "token": self.session.token,
            "product_id": state.get("product_id", ""),
            "product_name": state.get("product_name", ""),
            "state": state.get("state", ""),
            "current_step": state.get("current_step", 0),
            "total_steps": state.get("total_steps", 1),
            "last_result": state.get("last_result", "waiting"),
            "event": state.get("event", "state_change"),
            "defect_type": state.get("defect_type", ""),
            "detail": state.get("detail", ""),
        })

    def run(self) -> None:
        """Queue의 작업상태를 순서대로 Monitoring PC에 전송합니다."""
        self._running = True
        if self.session.is_test_session:
            self.status_changed.emit("상태 전송 테스트 모드", True)
        while self._running:
            try:
                payload = self._queue.get(timeout=0.4)
            except queue.Empty:
                continue
            if payload is None:
                break
            if self.session.is_test_session:
                continue
            try:
                response = send_json_request(payload)
                ok = response.get("ok")
                msg = "상태 전송 완료" if ok else response.get("message", "상태 전송 실패")
                self.status_changed.emit(msg, bool(ok))
            except (OSError, ValueError, ConnectionError) as error:
                self.status_changed.emit(f"상태 전송 실패: {error}", False)

    def logout_and_stop(self) -> None:
        """Monitoring PC에서 Session을 종료한 뒤 전송 Thread를 정리합니다."""
        if not self.session.is_test_session:
            try:
                send_json_request({"type": "logout", "token": self.session.token})
            except (OSError, ValueError, ConnectionError):
                pass
        self._running = False
        self._queue.put(None)
        self.wait(2500)
