"""Monitoring PC 관리자 프로그램의 실행 진입점입니다."""

import sys

from PyQt5.QtWidgets import QApplication, QMessageBox

import config
from admin_window import AdminWindow
from database_manager import DatabaseManager
from login_window import LoginWindow
from tcp_client import TcpClient, WorkerEndpointRegistry
from theme import apply_theme
from monitoring_gateway import MonitoringGatewayThread


class MonitoringApplication:
    """로그인 창과 관리자 창의 화면 전환을 관리합니다."""

    def __init__(self):
        self.database_manager = DatabaseManager()
        self.worker_endpoint_registry = WorkerEndpointRegistry()
        self.tcp_client = TcpClient(
            endpoint_registry=self.worker_endpoint_registry
        )
        self.login_window = None
        self.admin_window = None
        self.worker_gateway = None

    def set_worker_gateway(self, worker_gateway: MonitoringGatewayThread) -> None:
        """작업자 상태 신호를 현재 관리자 화면에 연결할 Gateway를 등록합니다."""
        self.worker_gateway = worker_gateway

    def start(self) -> bool:
        """DB를 초기화한 뒤 로그인 화면을 표시합니다."""
        try:
            self.database_manager.initialize_database()
            if config.AUTO_CREATE_SAMPLE_DATA:
                self.database_manager.insert_sample_data()
        except Exception as error:
            QMessageBox.critical(None, "초기화 오류", f"DB 초기화에 실패했습니다.\n{error}")
            return False
        self.show_login_window()
        return True

    def show_login_window(self) -> None:
        """관리자 로그인 화면을 엽니다."""
        if self.admin_window is not None:
            if self.worker_gateway is not None:
                try:
                    self.worker_gateway.worker_state_received.disconnect(
                        self.admin_window.queue_employee_refresh
                    )
                except (TypeError, RuntimeError):
                    pass
            self.admin_window.close()
            self.admin_window = None
        self.login_window = LoginWindow(self.database_manager)
        self.login_window.login_succeeded.connect(self.show_admin_window)
        self.login_window.show()

    def show_admin_window(self, admin_info: dict) -> None:
        """로그인 성공 시 관리자 메인 화면으로 전환합니다."""
        self.admin_window = AdminWindow(
            self.database_manager, self.tcp_client, admin_info
        )
        self.admin_window.logout_requested.connect(self.show_login_window)
        if self.worker_gateway is not None:
            self.worker_gateway.worker_state_received.connect(
                self.admin_window.queue_employee_refresh
            )
        self.admin_window.show()
        if self.login_window is not None:
            self.login_window.close()
            self.login_window = None


def main() -> int:
    """QApplication을 만들고 이벤트 루프를 시작합니다."""
    application = QApplication(sys.argv)
    application.setApplicationName("Monitoring PC")
    apply_theme(application)
    monitoring_application = MonitoringApplication()
    if not monitoring_application.start():
        return 1
    worker_gateway = MonitoringGatewayThread(
        monitoring_application.database_manager,
        endpoint_registry=monitoring_application.worker_endpoint_registry,
    )
    monitoring_application.set_worker_gateway(worker_gateway)
    worker_gateway.start()
    application.aboutToQuit.connect(worker_gateway.stop)
    return application.exec_()


if __name__ == "__main__":
    sys.exit(main())
