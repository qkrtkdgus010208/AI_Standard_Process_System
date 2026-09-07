"""STM32 UART 수신을 UI와 분리하여 처리하는 Thread 모듈입니다."""

import os
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

import config

try:
    import serial
except ImportError:
    serial = None


class UartReceiverThread(QThread):
    """Linux Serial Port에서 줄 단위 메시지를 계속 수신합니다."""

    message_received = pyqtSignal(str)
    status_changed = pyqtSignal(str, bool)

    def __init__(self, port: Optional[str] = None,
                 baudrate: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.port = port or config.UART_PORT
        self.baudrate = baudrate or config.UART_BAUDRATE
        self._running = False
        self._serial = None
        self._is_connected = False

    def is_connected(self) -> bool:
        """현재 UART 포트가 정상 연결되어 수신 중인지 반환합니다."""
        if config.TEST_MODE or not config.UART_ENABLED:
            return self._running and self.isRunning()
        return (
            self._is_connected
            and self.isRunning()
            and self._serial is not None
            and getattr(self._serial, "is_open", False)
        )

    def restart(self) -> None:
        """UART 스레드를 안전하게 중지한 후 재시작합니다."""
        self.stop()
        self.start()

    def run(self) -> None:
        """UART 연결 후 수신 Loop를 실행합니다."""
        self._running = True
        self._is_connected = False

        if config.TEST_MODE or not config.UART_ENABLED:
            self._is_connected = True
            self.status_changed.emit("UART 테스트 모드", True)
            while self._running:
                self.msleep(250)
            return

        if serial is None:
            self.status_changed.emit("pyserial이 설치되지 않았습니다.", False)
            return

        # 후보 포트 자동 탐색 (기본 설정 포트가 없으면 다른 시리얼 포트 확인)
        actual_port = self.port
        if not os.path.exists(actual_port):
            candidates = ["/dev/ttyACM0", "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM1", "/dev/ttyTHS1"]
            for candidate in candidates:
                if os.path.exists(candidate):
                    actual_port = candidate
                    break

        if not os.path.exists(actual_port):
            self.status_changed.emit(f"UART 포트 없음 ({self.port})", False)
            return

        try:
            self._serial = serial.Serial(
                port=actual_port,
                baudrate=self.baudrate,
                timeout=config.UART_TIMEOUT_SECONDS,
            )
            self.port = actual_port
            self._is_connected = True
            self.status_changed.emit(f"UART 연결: {actual_port}", True)
            while self._running:
                raw_line = self._serial.readline()
                if raw_line:
                    line_str = raw_line.decode("utf-8", errors="replace").strip()
                    if line_str:
                        self.message_received.emit(line_str)
        except PermissionError:
            self._is_connected = False
            self.status_changed.emit(f"UART 권한 오류: {actual_port} (sudo chmod 666 {actual_port})", False)
        except Exception as error:
            self._is_connected = False
            self.status_changed.emit(f"UART 연결 실패: {error}", False)
        finally:
            self._is_connected = False
            if self._serial is not None:
                try:
                    if self._serial.is_open:
                        self._serial.close()
                except OSError:
                    pass
            self._serial = None

    def send_message(self, message: str) -> bool:
        """STM32로 단일 명령 문자를 전송하며 연결되지 않은 경우 False를 반환합니다."""
        if config.TEST_MODE:
            return True
        if self._serial is None or not getattr(self._serial, "is_open", False):
            return False
        try:
            # 단일 문자 명령('S', 'P', 'F') 전송 시 불필요한 개행을 붙이지 않아 STM32 수신 버퍼 덮어쓰기 방지
            payload = message.strip().encode("utf-8")
            self._serial.write(payload)
            self._serial.flush()
            return True
        except Exception:
            return False

    def simulate_receive(self, message: str) -> None:
        """UART 수신 동작을 시험(시뮬레이션)합니다."""
        self.message_received.emit(message)

    def stop(self) -> None:
        """UART 수신 Loop와 Serial Port를 종료합니다."""
        self._running = False
        if self._serial is not None:
            try:
                self._serial.close()
            except OSError:
                pass
        if self.isRunning():
            self.wait(2000)
