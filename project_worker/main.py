"""Jetson 작업자 프로그램 실행 및 로그인/로그아웃 화면 전환입니다."""

from pathlib import Path
import signal
import sys

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox

from services.auth_manager import WorkerSession
from ui.login_window import WorkerLoginWindow
from ui.theme import apply_theme
from ui.worker_window import WorkerWindow


class WorkerApplication:
    """인증 Session과 로그인/작업 화면의 생명주기를 관리합니다."""

    def __init__(self):
        self.login_window = None
        self.worker_window = None
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
        self.worker_window = WorkerWindow(session)
        self.worker_window.logout_requested.connect(self.logout)
        self.worker_window.show()
        if self.login_window is not None:
            self.login_window.close()
            self.login_window = None

    def logout(self) -> None:
        """현재 작업자 Session을 종료하고 로그인 화면으로 돌아갑니다."""
        if self.worker_window is not None:
            self.worker_window.close()
            self.worker_window = None
        self.session = None
        self.show_login()

    def cleanup(self) -> None:
        """프로그램 전체 종료 시 남은 인증 Session을 정리합니다."""
        if self.worker_window is not None:
            self.worker_window.close()
            self.worker_window = None


def main() -> int:
    """QApplication과 작업자 Application Controller를 시작합니다."""
    application = QApplication(sys.argv)
    application.setApplicationName("Factory Worker PC")
    apply_theme(application)

    signal.signal(signal.SIGINT, lambda *_: application.quit())
    signal.signal(signal.SIGTERM, lambda *_: application.quit())
    sig_timer = QTimer()
    sig_timer.start(500)
    sig_timer.timeout.connect(lambda: None)

    try:
        worker_application = WorkerApplication()
        worker_application.start()
        application.aboutToQuit.connect(worker_application.cleanup)
        return application.exec_()
    except Exception as error:
        QMessageBox.critical(None, "프로그램 오류", f"프로그램 시작에 실패했습니다.\n{error}")
        return 1


def _verify_root_execution() -> None:
    """프로젝트 최상위 루트 디렉토리에서 실행되었는지 검증합니다."""
    project_root = Path(__file__).resolve().parent.parent
    current_dir = Path.cwd().resolve()
    if current_dir != project_root:
        sys.stderr.write(
            f"\n❌ [실행 오류] 본 프로그램은 반드시 프로젝트 최상위 루트 디렉토리에서 실행해야 합니다.\n"
            f"   현재 위치: {current_dir}\n"
            f"   프로젝트 루트: {project_root}\n\n"
            f"👉 실행 방법:\n"
            f"   cd {project_root}\n"
            f"   bash run_worker.sh\n\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    _verify_root_execution()
    sys.exit(main())
