"""Jetson 작업자 프로그램 실행 및 로그인/로그아웃 화면 전환입니다."""

import sys

from PyQt5.QtWidgets import QApplication, QMessageBox

from auth_manager import MonitoringEventThread, WorkerSession
from login_window import WorkerLoginWindow
from theme import apply_theme
from worker_window import WorkerWindow


class WorkerApplication:
    """인증 Session과 로그인/작업 화면의 생명주기를 관리합니다."""

    def __init__(self):
        self.login_window = None
        self.worker_window = None
        self.event_thread = None
        self.session = None

    def start(self) -> None:
        self.show_login()

    def show_login(self) -> None:
        """로그아웃된 상태의 작업자 로그인 화면을 표시합니다."""
        self.login_window = WorkerLoginWindow()
        self.login_window.login_succeeded.connect(self.show_worker)
        self.login_window.show()

    def show_worker(self, session: WorkerSession) -> None:
        """인증된 Session을 고정한 작업 화면을 표시합니다."""
        self.session = session
        self.event_thread = MonitoringEventThread(session)
        self.event_thread.start()
        self.worker_window = WorkerWindow(session)
        self.worker_window.work_controller.state_changed.connect(
            self.event_thread.enqueue_state
        )
        self.worker_window.logout_requested.connect(self.logout)
        self.worker_window.show()
        if self.login_window is not None:
            self.login_window.close()
            self.login_window = None

    def logout(self) -> None:
        """현재 작업자 Session을 종료하고 로그인 화면으로 돌아갑니다."""
        if self.event_thread is not None:
            self.event_thread.logout_and_stop()
            self.event_thread = None
        if self.worker_window is not None:
            self.worker_window.close()
            self.worker_window = None
        self.session = None
        self.show_login()

    def cleanup(self) -> None:
        """프로그램 전체 종료 시 남은 인증 Session을 정리합니다."""
        if self.event_thread is not None:
            self.event_thread.logout_and_stop()
            self.event_thread = None


def main() -> int:
    """QApplication과 작업자 Application Controller를 시작합니다."""
    application = QApplication(sys.argv)
    application.setApplicationName("Factory Worker PC")
    apply_theme(application)
    try:
        worker_application = WorkerApplication()
        worker_application.start()
        application.aboutToQuit.connect(worker_application.cleanup)
        return application.exec_()
    except Exception as error:
        QMessageBox.critical(None, "프로그램 오류", f"프로그램 시작에 실패했습니다.\n{error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
