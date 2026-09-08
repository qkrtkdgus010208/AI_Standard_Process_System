"""Monitoring PC 서버 연결 상태를 주기적으로 감시하는 모듈입니다.

서버 연결 끊김을 감지하면 콜백을 호출합니다.
WorkerWindow에서 서버 감시 책임을 분리합니다.
"""

from typing import Callable, Optional

from PyQt5.QtCore import QTimer

import config
from network.network_client import ServerCheckThread


class ServerMonitor:
    """서버 연결 상태를 주기적으로 점검하는 감시자입니다.

    서버 연결 끊김 시 `on_disconnected` 콜백을 호출합니다.
    """

    def __init__(
        self,
        parent,
        on_disconnected: Callable[[str], None],
        interval_ms: int = 2000,
    ):
        """
        Args:
            parent: QObject 부모 (타이머 소유권)
            on_disconnected: 서버 연결 끊김 시 호출할 콜백 (reason: str)
            interval_ms: 점검 주기 (밀리초)
        """
        self._on_disconnected = on_disconnected
        self._check_thread: Optional[ServerCheckThread] = None
        self._is_terminating = False

        self._timer = QTimer(parent)
        self._timer.timeout.connect(self._check)
        self._interval_ms = interval_ms

    # ── 공개 인터페이스 ──────────────────────────────────────────────────────

    def start(self) -> None:
        """서버 연결 감시를 시작합니다."""
        self._timer.start(self._interval_ms)

    def stop(self) -> None:
        """서버 연결 감시를 중단합니다."""
        self._timer.stop()
        if self._check_thread is not None and self._check_thread.isRunning():
            self._check_thread.wait(1000)

    def set_terminating(self) -> None:
        """프로그램 종료 중임을 표시하여 연결 끊김 알림을 억제합니다."""
        self._is_terminating = True
        self.stop()

    # ── 내부 구현 ────────────────────────────────────────────────────────────

    def _check(self) -> None:
        """백그라운드에서 서버 연결 상태를 비동기로 점검합니다."""
        if config.TEST_MODE or self._is_terminating:
            return
        if self._check_thread is not None and self._check_thread.isRunning():
            return
        self._check_thread = ServerCheckThread(timeout=1.0)
        self._check_thread.check_finished.connect(self._on_check_finished)
        self._check_thread.finished.connect(self._clear_check_thread)
        self._check_thread.start()

    def _clear_check_thread(self) -> None:
        self._check_thread = None

    def _on_check_finished(self, ok: bool, message: str) -> None:
        if not self._is_terminating and not ok:
            self._on_disconnected(message)
