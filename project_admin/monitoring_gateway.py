"""WorkerPC 인증과 세션 기반 상태 메시지를 받는 Monitoring PC 서버입니다."""

import json
import secrets
import socket
from concurrent.futures import ThreadPoolExecutor
from threading import RLock

from PyQt5.QtCore import QThread, pyqtSignal

import config
from database_manager import DatabaseManager
from tcp_client import WorkerEndpointRegistry


WORKER_GATEWAY_HOST = config.WORKER_GATEWAY_HOST
WORKER_GATEWAY_PORT = config.WORKER_GATEWAY_PORT
WORKER_GATEWAY_MAX_CLIENTS = config.WORKER_GATEWAY_MAX_CLIENTS


class MonitoringGatewayThread(QThread):
    """작업자를 인증하고 Token 소유자의 데이터만 허용하는 TCP Gateway입니다."""

    status_changed = pyqtSignal(str, bool)
    worker_state_received = pyqtSignal(dict)

    def __init__(self, database_manager: DatabaseManager,
                 host: str = WORKER_GATEWAY_HOST,
                 port: int = WORKER_GATEWAY_PORT,
                 max_clients: int = WORKER_GATEWAY_MAX_CLIENTS,
                 endpoint_registry: WorkerEndpointRegistry | None = None,
                 parent=None):
        super().__init__(parent)
        self.database_manager = database_manager
        self.host = host
        self.port = port
        self.max_clients = max(1, int(max_clients))
        self._running = False
        self._server_socket = None
        self._sessions = {}
        self._sessions_lock = RLock()
        self.endpoint_registry = endpoint_registry or WorkerEndpointRegistry()

    def run(self) -> None:
        """JSON 한 줄 요청을 받아 인증·상태·로그아웃을 처리합니다."""
        self._running = True
        try:
            with ThreadPoolExecutor(max_workers=self.max_clients) as executor, \
                    socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                self._server_socket = server_socket
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.settimeout(0.5)
                server_socket.bind((self.host, self.port))
                server_socket.listen(self.max_clients * 2)
                self.port = server_socket.getsockname()[1]
                self.status_changed.emit(
                    f"작업자 인증 서버 대기: {self.host}:{self.port}", True
                )
                while self._running:
                    try:
                        client, address = server_socket.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    executor.submit(self._handle_client, client, address[0])
        except OSError as error:
            self.status_changed.emit(f"작업자 인증 서버 오류: {error}", False)
        finally:
            self._server_socket = None

    def _handle_client(self, client: socket.socket, client_ip: str) -> None:
        """Client 요청 하나를 읽고 JSON 응답을 반환합니다."""
        with client:
            client.settimeout(2.0)
            try:
                buffer = b""
                while b"\n" not in buffer and len(buffer) < 65536:
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk
                request = json.loads(buffer.decode("utf-8").splitlines()[0])
                response = self._process_request(request, client_ip)
            except (OSError, ValueError, IndexError, json.JSONDecodeError) as error:
                response = {"ok": False, "message": f"잘못된 요청입니다: {error}"}
            client.sendall((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))

    def _process_request(self, request: dict, client_ip: str = "127.0.0.1") -> dict:
        """요청 종류에 따라 인증 또는 Token 검증을 수행합니다."""
        request_type = str(request.get("type", "")).lower()
        if request_type == "auth":
            employee = self.database_manager.verify_worker_login(
                str(request.get("employee_id", "")), str(request.get("password", ""))
            )
            if employee is None:
                return {"ok": False, "message": "직원번호 또는 비밀번호가 올바르지 않습니다."}
            token = secrets.token_urlsafe(32)
            displaced_sessions = []
            with self._sessions_lock:
                displaced_tokens = self.endpoint_registry.bind(
                    employee["employee_id"], client_ip, token
                )
                for displaced_token in displaced_tokens:
                    displaced_session = self._sessions.pop(displaced_token, None)
                    if displaced_session is not None:
                        displaced_sessions.append(displaced_session)
                self._sessions[token] = {"employee": employee, "client_ip": client_ip}
            for displaced_session in displaced_sessions:
                if (
                    displaced_session["employee"]["employee_id"]
                    != employee["employee_id"]
                ):
                    displaced_employee_id = displaced_session["employee"]["employee_id"]
                    self.database_manager.end_work_session(displaced_employee_id)
                    self.worker_state_received.emit({
                        "employee_id": displaced_employee_id,
                        "event": "logout",
                    })
            self.database_manager.start_work_session(employee["employee_id"])
            work_state = self.database_manager.get_incomplete_work_state(
                employee["employee_id"]
            )
            self.worker_state_received.emit({
                "employee_id": employee["employee_id"],
                "event": "auth",
            })
            return {
                "ok": True,
                "token": token,
                "employee": employee,
                "work_state": work_state,
            }

        token = str(request.get("token", ""))
        with self._sessions_lock:
            session = self._sessions.get(token)
        if session is None:
            return {"ok": False, "message": "유효하지 않거나 만료된 로그인 세션입니다."}
        if session["client_ip"] != client_ip:
            return {"ok": False, "message": "로그인한 Jetson과 요청 주소가 다릅니다."}
        employee = session["employee"]

        if request_type in ("products", "get_products"):
            products = self.database_manager.search_products("")
            return {
                "ok": True,
                "products": [
                    {
                        "product_id": str(product["product_id"]),
                        "product_name": str(product["product_name"]),
                        "total_steps": int(product["total_steps"]),
                    }
                    for product in products
                ],
            }

        if request_type == "state":
            state = {
                "employee_id": employee["employee_id"],
                "name": employee["name"],
                "product_id": str(request.get("product_id", "")),
                "product_name": str(request.get("product_name", "")),
                "state": str(request.get("state", "")),
                "current_step": int(request.get("current_step", 1)),
                "total_steps": int(request.get("total_steps", 1)),
                "last_result": str(request.get("last_result", "waiting")),
                "event": str(request.get("event", "")),
                "defect_type": str(request.get("defect_type", "")),
                "detail": str(request.get("detail", "")),
            }
            try:
                self.database_manager.record_worker_state(state)
            except ValueError as error:
                return {"ok": False, "message": str(error)}
            self.worker_state_received.emit(state)
            return {"ok": True}

        if request_type == "logout":
            self.database_manager.end_work_session(employee["employee_id"])
            with self._sessions_lock:
                self.endpoint_registry.unbind(employee["employee_id"], token)
                self._sessions.pop(token, None)
            self.worker_state_received.emit({
                "employee_id": employee["employee_id"],
                "event": "logout",
            })
            return {"ok": True}

        return {"ok": False, "message": "지원하지 않는 요청입니다."}

    def stop(self) -> None:
        """Gateway와 모든 Memory Session을 안전하게 종료합니다."""
        self._running = False
        with self._sessions_lock:
            self._sessions.clear()
            self.endpoint_registry.clear()
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
        self.wait(2500)
        with self._sessions_lock:
            self._sessions.clear()
            self.endpoint_registry.clear()
