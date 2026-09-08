"""WorkerPC 인증과 세션 기반 상태 메시지를 받는 Monitoring PC 서버입니다."""

import base64
import json
import secrets
import socket
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, RLock

from PyQt5.QtCore import QThread, pyqtSignal

import config
from db.database_manager import DatabaseManager
from models.state_types import (
    EmployeeIdentity,
    GatewaySession,
    StateRequest,
    WorkerStateInput,
)
from network.tcp_client import WorkerEndpointRegistry
from services.step_guide_storage import resolve_guide_path


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
        self._sessions: dict[str, GatewaySession] = {}
        self._sessions_lock = RLock()
        self._employee_locks = {}
        self.endpoint_registry = endpoint_registry or WorkerEndpointRegistry()

    def _employee_lock(self, employee_id: str) -> Lock:
        """직원별 auth/state/logout 세대 전이를 직렬화할 Lock을 반환합니다."""
        with self._sessions_lock:
            return self._employee_locks.setdefault(employee_id, Lock())

    def _session_matches(
        self, token: str, employee: EmployeeIdentity, client_ip: str
    ) -> bool:
        """현재 token이 같은 직원·IP에 아직 귀속되어 있는지 확인합니다."""
        with self._sessions_lock:
            session = self._sessions.get(token)
            return bool(
                session is not None
                and session["client_ip"] == client_ip
                and session["employee"]["employee_id"] == employee["employee_id"]
            )

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
        """요청 종류에 따라 인증 또는 Token 검증 후 해당 핸들러로 전달합니다."""
        request_type = str(request.get("type", "")).lower()
        if request_type == "auth":
            return self._handle_auth_request(request, client_ip)

        token = str(request.get("token", ""))
        with self._sessions_lock:
            session = self._sessions.get(token)
        if session is None:
            return {"ok": False, "message": "유효하지 않거나 만료된 로그인 세션입니다."}
        if session["client_ip"] != client_ip:
            return {"ok": False, "message": "로그인한 Jetson과 요청 주소가 다릅니다."}
        employee = session["employee"]

        if request_type in ("products", "get_products"):
            return self._handle_products_request()
        if request_type == "step_guide":
            return self._handle_step_guide_request(request)
        if request_type == "state":
            return self._handle_state_request(request, employee, token, client_ip)
        if request_type == "logout":
            return self._handle_logout_request(employee, token, client_ip)

        return {"ok": False, "message": "지원하지 않는 요청입니다."}

    def _handle_auth_request(self, request: dict, client_ip: str) -> dict:
        """작업자 로그인 인증을 수행하고 토큰 및 이전 작업 상태를 발급합니다."""
        employee = self.database_manager.verify_worker_login(
            str(request.get("employee_id", "")), str(request.get("password", ""))
        )
        if employee is None:
            return {"ok": False, "message": "직원번호 또는 비밀번호가 올바르지 않습니다."}

        employee_id = employee["employee_id"]
        with self._employee_lock(employee_id):
            token = secrets.token_urlsafe(32)
            displaced_sessions = []
            with self._sessions_lock:
                displaced_tokens = self.endpoint_registry.bind(
                    employee_id, client_ip, token
                )
                for displaced_token in displaced_tokens:
                    displaced_session = self._sessions.pop(displaced_token, None)
                    if displaced_session is not None:
                        displaced_sessions.append(displaced_session)
                self._sessions[token] = {"employee": employee, "client_ip": client_ip}

                for displaced_session in displaced_sessions:
                    if displaced_session["employee"]["employee_id"] != employee_id:
                        displaced_employee_id = displaced_session["employee"]["employee_id"]
                        self.database_manager.end_work_session(displaced_employee_id)

                self.database_manager.start_work_session(employee_id)
            work_state = self.database_manager.get_incomplete_work_state(employee_id)
        for displaced_session in displaced_sessions:
            if displaced_session["employee"]["employee_id"] != employee_id:
                self.worker_state_received.emit({
                    "employee_id": displaced_session["employee"]["employee_id"],
                    "event": "logout",
                })
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

    def _handle_products_request(self) -> dict:
        """등록된 제품 목록을 조회하여 반환합니다."""
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

    def _handle_step_guide_request(self, request: dict) -> dict:
        """현재 제품·STEP의 기준 이미지 한 장을 Base64로 반환합니다."""
        product_id = str(request.get("product_id", "")).strip()
        try:
            step_no = int(request.get("step_no", 0))
        except (TypeError, ValueError):
            return {"ok": False, "message": "STEP 번호가 올바르지 않습니다."}
        product = self.database_manager.get_product(product_id)
        if product is None:
            return {"ok": False, "message": "등록되지 않은 제품입니다."}
        if step_no < 1 or step_no > int(product["total_steps"]):
            return {"ok": False, "message": "제품의 STEP 범위를 벗어났습니다."}

        guide = self.database_manager.get_product_step_guide(product_id, step_no)
        if guide is None:
            return {"ok": True, "guide": None}
        try:
            path = resolve_guide_path(guide["image_path"])
            image_data = path.read_bytes()
        except (OSError, ValueError) as error:
            return {"ok": False, "message": f"기준 이미지를 읽을 수 없습니다: {error}"}
        if len(image_data) > config.STEP_GUIDE_MAX_RESPONSE_BYTES:
            return {"ok": False, "message": "기준 이미지 용량이 전송 제한을 초과합니다."}
        return {
            "ok": True,
            "guide": {
                "product_id": product_id,
                "step_no": step_no,
                "mime_type": guide["mime_type"],
                "sha256": guide["sha256"],
                "updated_at": guide["updated_at"],
                "image_base64": base64.b64encode(image_data).decode("ascii"),
            },
        }

    def _handle_state_request(
        self, request: StateRequest, employee: EmployeeIdentity,
        token: str, client_ip: str,
    ) -> dict:
        """수신된 작업자 공정 상태를 DB에 저장하고 모니터링 이벤트로 통지합니다."""
        state: WorkerStateInput = {
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
            "client_event_id": request.get("event_id"),
        }
        with self._employee_lock(employee["employee_id"]):
            with self._sessions_lock:
                if not self._session_matches(token, employee, client_ip):
                    return {"ok": False, "message": "유효하지 않거나 만료된 로그인 세션입니다."}
                try:
                    state_event_id = self.database_manager.record_worker_state(state)
                except ValueError as error:
                    return {"ok": False, "message": str(error)}
        if state_event_id is not None:
            self.worker_state_received.emit(state)
        return {"ok": True}

    def _handle_logout_request(
        self, employee: EmployeeIdentity, token: str, client_ip: str
    ) -> dict:
        """작업 세션을 종료하고 토큰을 해제합니다."""
        with self._employee_lock(employee["employee_id"]):
            with self._sessions_lock:
                if not self._session_matches(token, employee, client_ip):
                    return {"ok": False, "message": "유효하지 않거나 만료된 로그인 세션입니다."}
                self.database_manager.end_work_session(employee["employee_id"])
                self.endpoint_registry.unbind(employee["employee_id"], token)
                self._sessions.pop(token, None)
        self.worker_state_received.emit({
            "employee_id": employee["employee_id"],
            "event": "logout",
        })
        return {"ok": True}

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
