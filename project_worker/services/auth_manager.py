"""작업자 인증 세션을 담당하는 모듈입니다.

로그인 인증 요청 및 세션 정보 관리를 전담합니다.
네트워크 통신: network_client.py
제품 목록 조회: product_service.py
상태 전송: state_reporter.py
"""

from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

import config
from network.network_client import (
    ServerCheckThread,
    check_monitoring_server_connection,
    send_json_request,
)
from services.product_service import (
    ProductFetchThread,
    ProductInfo,
    fetch_products_from_monitoring_pc,
    parse_product_item,
)
from services.state_reporter import MonitoringEventThread, parse_work_state_data


@dataclass(frozen=True)
class WorkerSession:
    """로그인 후 변경할 수 없는 작업자 신원과 Session Token입니다."""

    employee_id: str
    name: str
    role: str
    token: str
    is_test_session: bool = False
    saved_state: Optional[dict] = None


@dataclass(frozen=True)
class AuthResult:
    """인증 성공 여부와 Session 또는 오류 메시지를 담습니다."""

    success: bool
    message: str
    session: Optional[WorkerSession] = None


class AuthRequestThread(QThread):
    """로그인 인증 Network 요청을 UI와 분리하여 실행합니다."""

    completed = pyqtSignal(object)

    def __init__(self, employee_id: str, password: str, parent=None):
        super().__init__(parent)
        self.employee_id = employee_id.strip()
        self.password = password
        self.finished.connect(self.deleteLater)

    def run(self) -> None:
        """TEST_MODE Mock 인증 또는 실제 Monitoring PC 인증을 실행합니다."""
        if config.TEST_MODE:
            if self.employee_id == "1001" and self.password == "worker1234":
                self.completed.emit(AuthResult(
                    True, "로그인 성공",
                    WorkerSession("1001", "홍길동", "worker", "test-session", True),
                ))
            else:
                self.completed.emit(AuthResult(False, "직원번호 또는 비밀번호를 확인하세요."))
            return
        try:
            response = send_json_request({
                "type": "auth",
                "employee_id": self.employee_id,
                "password": self.password,
            })
            if not response.get("ok"):
                self.completed.emit(AuthResult(False, response.get("message", "로그인 실패")))
                return
            employee = response["employee"]
            saved_raw = (
                response.get("work_state")
                or response.get("state")
                or employee.get("work_state")
            )
            session = WorkerSession(
                employee_id=str(employee["employee_id"]),
                name=str(employee["name"]),
                role=str(employee["role"]),
                token=str(response["token"]),
                saved_state=parse_work_state_data(saved_raw),
            )
            self.completed.emit(AuthResult(True, "로그인 성공", session))
        except (OSError, ValueError, KeyError, ConnectionError) as error:
            self.completed.emit(AuthResult(False, f"Monitoring PC 연결 실패: {error}"))
