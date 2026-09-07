"""STM32 UART 명령 전송을 캡슐화하는 컨트롤러 모듈입니다.

모든 STM32 관련 UART 명령 전송과 로그 기록을 한 곳에서 관리합니다.
반복적인 'uart_thread.send_message() + add_log()' 패턴을 제거합니다.
"""

from typing import Callable, Optional

from PyQt5.QtCore import QThread


class StmController:
    """STM32 UART 명령 전송을 책임지는 컨트롤러입니다.

    UartReceiverThread와 로그 콜백을 주입받아 모든 UART 명령 전송을
    중앙에서 처리합니다.

    UART 프로토콜 (Qt → STM32):
        'S': 작업 시작
        'P': PASS (다음 STEP)
        'F': AI FAIL
        'C': 전체 완료
        'R': 불량 등록 / 수동 리셋
        'U': 일시정지
        'M': 작업 재개
        'E': 프로그램 종료/로그아웃
        '1'~'9': 서버 복원 (STEP n LED ON)
    """

    def __init__(self, uart_thread, log_callback: Callable[[str, str], None]):
        """
        Args:
            uart_thread: UartReceiverThread 인스턴스
            log_callback: add_log(level, message) 형태의 로그 콜백 함수
        """
        self._uart = uart_thread
        self._log = log_callback
        self._exit_sent = False

    def _send(self, cmd: str, success_level: str, success_msg: str,
              fail_msg: Optional[str] = None) -> bool:
        """UART 명령을 전송하고 결과에 따라 로그를 기록합니다."""
        if self._uart.send_message(cmd):
            self._log(success_level, success_msg)
            return True
        else:
            self._log("warning", fail_msg or f"[UART 송신 실패] {cmd} (시리얼 포트 미연결)")
            return False

    def send_start(self) -> bool:
        """작업 시작 명령('S')을 전송합니다."""
        return self._send("S", "info", "[UART 송신] S → STM32 작업 시작 명령 전달")

    def send_pass(self) -> bool:
        """PASS 명령('P')을 전송합니다 (다음 STEP 진입)."""
        return self._send(
            "P", "success",
            "[UART 송신] P → STM32 PASS 전달 (정상 LED/부저, 다음 STEP 진입)",
        )

    def send_fail(self) -> bool:
        """AI FAIL 명령('F')을 전송합니다."""
        return self._send("F", "error", "[UART 송신] F → STM32 FAIL 전달 (불량 LED/부저 경보)")

    def send_complete(self) -> bool:
        """전체 공정 완료 명령('C')을 전송합니다."""
        return self._send(
            "C", "success",
            "[UART 송신] C → STM32 공정 완료 전달 (작업 완료 부저 및 STEP 0 초기화)",
        )

    def send_defect(self) -> bool:
        """불량 등록/리셋 명령('R')을 전송합니다."""
        return self._send("R", "error", "[UART 송신] R → STM32 수동 불량 등록 전달 (불량처리 부저)")

    def send_pause(self) -> bool:
        """일시정지 명령('U')을 전송합니다."""
        return self._send(
            "U", "warning",
            "[UART 송신] U → STM32 공정 일시정지 전달 (일시정지 부저)",
        )

    def send_resume(self) -> bool:
        """작업 재개 명령('M')을 전송합니다."""
        return self._send(
            "M", "info",
            "[UART 송신] M → STM32 공정 작업 재개 전달 (작업재개 부저)",
        )

    def send_exit(self) -> None:
        """프로그램 종료/대기 상태 전환 명령('E')을 전송합니다 (중복 전송 방지)."""
        if self._exit_sent:
            return
        self._exit_sent = True
        try:
            if self._uart.send_message("E"):
                self._log("info", "[UART 송신] E → STM32 프로그램 종료/대기 상태 전환")
            QThread.msleep(50)
        except Exception:
            pass

    def send_step_restore(self, current_step: int, state: str) -> bool:
        """서버에서 복원된 작업 상태(STEP, 일시정지)를 STM32로 전송하여 하드웨어를 동기화합니다."""
        if not (1 <= current_step <= 9):
            return False

        # UART 스레드가 포트에 정상 연결될 때까지 대기 (최대 1.5초)
        for _ in range(15):
            if self._uart.is_connected():
                break
            QThread.msleep(100)

        # 해당 STEP으로 복원 (STEP LED 점등, 버튼 활성화)
        step_char = str(current_step)
        if self._uart.send_message(step_char):
            self._log(
                "info",
                f"[UART 송신] {step_char} → STM32 이전 작업 복원 (STEP {current_step} LED 점등 및 버튼 활성화)",
            )
        else:
            self._log("warning", f"[UART 송신 실패] {step_char} (시리얼 포트 미연결)")
            return False

        # 일시정지 상태인 경우 일시정지 명령('U') 추가 전송
        if state == "paused":
            QThread.msleep(100)
            if self._uart.send_message("U"):
                self._log("warning", "[UART 송신] U → STM32 복원 작업 일시정지 반영 (일시정지 부저)")
            else:
                self._log("warning", "[UART 송신 실패] U (시리얼 포트 미연결)")

        return True

    def send_standby(self) -> None:
        """복원할 이전 작업이 없는 경우 STM32를 안전한 대기 상태('E')로 설정합니다."""
        for _ in range(10):
            if self._uart.is_connected():
                break
            QThread.msleep(100)
        if self._uart.send_message("E"):
            self._log("info", "[UART 송신] E → STM32 초기 대기 상태 설정 (LED 소등 및 버튼 비활성화)")
