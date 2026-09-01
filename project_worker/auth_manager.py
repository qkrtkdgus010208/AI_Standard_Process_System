"""작업자 인증 세션과 Monitoring PC 상태 전송을 담당합니다."""

import json
import queue
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from PyQt5.QtCore import QThread, pyqtSignal

import config


@dataclass(frozen=True)
class WorkerSession:
    """로그인 후 변경할 수 없는 작업자 신원과 Session Token입니다."""

    employee_id: str
    name: str
    role: str
    token: str
    is_test_session: bool = False


@dataclass(frozen=True)
class ProductInfo:
    """모니터링 PC SQLite DB products 테이블에서 조회한 제품 정보입니다."""

    product_id: str
    product_name: str
    total_steps: int


@dataclass(frozen=True)
class AuthResult:
    """인증 성공 여부와 Session 또는 오류 메시지를 담습니다."""

    success: bool
    message: str
    session: Optional[WorkerSession] = None


def send_json_request(payload: dict) -> dict:
    """Monitoring PC Gateway에 JSON 한 줄 요청을 보내고 응답을 받습니다."""
    with socket.create_connection(
        (config.MONITORING_PC_IP, config.MONITORING_AUTH_PORT),
        timeout=config.MONITORING_REQUEST_TIMEOUT_SECONDS,
    ) as client:
        client.settimeout(config.MONITORING_REQUEST_TIMEOUT_SECONDS)
        client.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        buffer = b""
        while b"\n" not in buffer and len(buffer) < 65536:
            chunk = client.recv(4096)
            if not chunk:
                break
            buffer += chunk
    if not buffer:
        raise ConnectionError("Monitoring PC에서 응답이 없습니다.")
    return json.loads(buffer.decode("utf-8").splitlines()[0])


class AuthRequestThread(QThread):
    """로그인 인증 Network 요청을 UI와 분리하여 실행합니다."""

    completed = pyqtSignal(object)

    def __init__(self, employee_id: str, password: str, parent=None):
        super().__init__(parent)
        self.employee_id = employee_id.strip()
        self.password = password

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
                "type": "auth", "employee_id": self.employee_id,
                "password": self.password,
            })
            if not response.get("ok"):
                self.completed.emit(AuthResult(False, response.get("message", "로그인 실패")))
                return
            employee = response["employee"]
            session = WorkerSession(
                employee_id=str(employee["employee_id"]),
                name=str(employee["name"]),
                role=str(employee["role"]),
                token=str(response["token"]),
            )
            self.completed.emit(AuthResult(True, "로그인 성공", session))
        except (OSError, ValueError, KeyError, ConnectionError) as error:
            self.completed.emit(AuthResult(False, f"Monitoring PC 연결 실패: {error}"))


def parse_product_item(item: Union[dict, list, tuple]) -> Optional[ProductInfo]:
    """모니터링 PC 응답 아이템을 ProductInfo로 변환합니다."""
    if isinstance(item, dict):
        pid = str(
            item.get("product_id")
            or item.get("id")
            or item.get("code")
            or item.get("product_code")
            or ""
        ).strip()
        pname = str(
            item.get("product_name")
            or item.get("name")
            or item.get("title")
            or item.get("item_name")
            or ""
        ).strip()
        total_steps = 1
        for k in ("total_steps", "steps", "total_step", "step_count", "process_count"):
            if k in item:
                try:
                    total_steps = int(item[k])
                    break
                except (ValueError, TypeError):
                    pass
        if pid and pname:
            return ProductInfo(product_id=pid, product_name=pname, total_steps=max(1, total_steps))
    elif isinstance(item, (list, tuple)) and len(item) >= 2:
        pid = str(item[0]).strip()
        pname = str(item[1]).strip()
        total_steps = 1
        if len(item) > 2:
            try:
                total_steps = int(item[2])
            except (ValueError, TypeError):
                total_steps = 1
        if pid and pname:
            return ProductInfo(product_id=pid, product_name=pname, total_steps=max(1, total_steps))
    return None


def fetch_products_from_monitoring_pc(token: str = "") -> list[ProductInfo]:
    """모니터링 PC Gateway에 요청하여 products 테이블의 제품 목록을 조회합니다."""
    types_to_try = ["products", "get_products"]
    last_error_message = None

    for req_type in types_to_try:
        try:
            payload = {"type": req_type}
            if token:
                payload["token"] = token
            response = send_json_request(payload)
            if not isinstance(response, dict):
                continue
            if response.get("ok") is False:
                last_error_message = response.get("message", "요청 실패")
                continue

            raw_list = (
                response.get("products")
                or response.get("data")
                or response.get("items")
                or response.get("product_list")
                or []
            )
            if isinstance(raw_list, list):
                products = []
                for item in raw_list:
                    prod = parse_product_item(item)
                    if prod is not None:
                        products.append(prod)
                return products
        except (OSError, ConnectionError, ValueError) as err:
            last_error_message = f"네트워크 오류: {err}"
            break

    if last_error_message:
        raise ConnectionError(last_error_message)
    return []


class ProductFetchThread(QThread):
    """모니터링 PC의 products 테이블에서 제품 목록을 비동기 조회하는 Thread입니다."""

    products_fetched = pyqtSignal(list, bool, str)

    def __init__(self, token: str = "", parent=None):
        super().__init__(parent)
        self.token = token

    def run(self) -> None:
        """모니터링 PC에 제품 목록을 요청하여 UI에 전달합니다."""
        if config.TEST_MODE:
            fallback = [
                ProductInfo(p["product_id"], p["product_name"], int(p["total_steps"]))
                for p in getattr(config, "DEFAULT_PRODUCTS", [])
            ]
            self.products_fetched.emit(
                fallback, True, f"TEST MODE 제품 {len(fallback)}건 로드 완료"
            )
            return

        try:
            products = fetch_products_from_monitoring_pc(self.token)
            if products:
                self.products_fetched.emit(
                    products, True, f"모니터링 PC에서 제품 {len(products)}건 로드 완료"
                )
            else:
                self.products_fetched.emit(
                    [], False, "모니터링 PC의 products 테이블에 등록된 제품이 없습니다."
                )
        except Exception as error:
            self.products_fetched.emit([], False, f"모니터링 PC 제품 조회 실패: {error}")


class MonitoringEventThread(QThread):
    """인증 Session Token으로 작업상태를 비동기 전송합니다."""

    status_changed = pyqtSignal(str, bool)

    def __init__(self, session: WorkerSession, parent=None):
        super().__init__(parent)
        self.session = session
        self._queue = queue.Queue()
        self._running = False

    def enqueue_state(self, state: dict) -> None:
        """직원번호 입력 없이 현재 Session 소유자의 상태만 Queue에 넣습니다."""
        payload = {
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
        }
        self._queue.put(payload)

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
                if not response.get("ok"):
                    self.status_changed.emit(response.get("message", "상태 전송 실패"), False)
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
