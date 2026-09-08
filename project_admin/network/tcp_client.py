"""Jetson 측 PC와의 TCP 통신을 담당하는 모듈입니다."""

from __future__ import annotations

import socket
import base64
from dataclasses import dataclass
from threading import RLock
from typing import Optional

import config

JETSON_SERVER_PORT = config.JETSON_SERVER_PORT
CONNECTION_TIMEOUT_SECONDS = config.JETSON_CONNECTION_TIMEOUT_SECONDS


@dataclass(frozen=True)
class SendResult:
    """TCP 전송 결과를 UI가 쉽게 처리할 수 있게 담습니다."""

    success: bool
    message: str


@dataclass(frozen=True)
class WorkerEndpoint:
    """로그인한 작업자와 현재 Jetson 접속 주소의 연결 정보입니다."""

    employee_id: str
    ip_address: str
    token: str


class WorkerEndpointRegistry:
    """활성 로그인 세션의 직원↔Jetson IP 연결을 Thread-safe하게 관리합니다."""

    def __init__(self):
        self._lock = RLock()
        self._by_employee: dict[str, WorkerEndpoint] = {}
        self._employee_by_ip: dict[str, str] = {}

    def bind(self, employee_id: str, ip_address: str, token: str) -> set[str]:
        """최신 로그인을 연결하고 대체된 이전 Token들을 반환합니다."""
        endpoint = WorkerEndpoint(employee_id, ip_address, token)
        displaced_tokens: set[str] = set()
        with self._lock:
            previous = self._by_employee.get(employee_id)
            if previous is not None:
                displaced_tokens.add(previous.token)
                if self._employee_by_ip.get(previous.ip_address) == employee_id:
                    self._employee_by_ip.pop(previous.ip_address, None)

            previous_employee = self._employee_by_ip.get(ip_address)
            if previous_employee is not None and previous_employee != employee_id:
                previous_endpoint = self._by_employee.pop(previous_employee, None)
                if previous_endpoint is not None:
                    displaced_tokens.add(previous_endpoint.token)

            self._by_employee[employee_id] = endpoint
            self._employee_by_ip[ip_address] = employee_id
        displaced_tokens.discard(token)
        return displaced_tokens

    def resolve(self, employee_id: str) -> Optional[str]:
        """직원이 로그인한 Jetson IP를 반환합니다."""
        with self._lock:
            endpoint = self._by_employee.get(employee_id)
            return endpoint.ip_address if endpoint else None

    def unbind(self, employee_id: str, token: str) -> None:
        """현재 연결의 Token과 일치할 때만 로그아웃 연결을 제거합니다."""
        with self._lock:
            endpoint = self._by_employee.get(employee_id)
            if endpoint is None or endpoint.token != token:
                return
            self._by_employee.pop(employee_id, None)
            if self._employee_by_ip.get(endpoint.ip_address) == employee_id:
                self._employee_by_ip.pop(endpoint.ip_address, None)

    def clear(self) -> None:
        """관제 Gateway 종료 시 모든 임시 연결을 제거합니다."""
        with self._lock:
            self._by_employee.clear()
            self._employee_by_ip.clear()


def build_employee_message(employee_id: str, message_text: str) -> str:
    """구분자와 줄바꿈이 포함된 한글 메시지도 안전하게 전송하도록 인코딩합니다."""
    encoded_text = base64.urlsafe_b64encode(
        message_text.encode("utf-8")
    ).decode("ascii")
    return f"MESSAGE|{employee_id}|{encoded_text}"


class TcpClient:
    """필요할 때 연결하여 메시지를 전송하고 즉시 연결을 닫습니다."""

    def __init__(self, server_ip: Optional[str] = None,
                 server_port=JETSON_SERVER_PORT,
                 timeout=CONNECTION_TIMEOUT_SECONDS,
                 endpoint_registry: Optional[WorkerEndpointRegistry] = None):
        self.server_ip = server_ip
        self.server_port = server_port
        self.timeout = timeout
        self.endpoint_registry = endpoint_registry

    def send_message(self, message: str, server_ip: Optional[str] = None) -> SendResult:
        """문자열 메시지를 UTF-8로 보내며 실패를 예외 대신 결과로 반환합니다."""
        target_ip = server_ip or self.server_ip
        if target_ip is None:
            return SendResult(False, "메시지를 보낼 Jetson 주소가 지정되지 않았습니다.")
        try:
            with socket.create_connection(
                (target_ip, self.server_port), timeout=self.timeout
            ) as client_socket:
                client_socket.sendall((message + "\n").encode("utf-8"))
            return SendResult(True, f"메시지를 전송했습니다: {message}")
        except (ConnectionError, OSError, socket.timeout) as error:
            return SendResult(
                False,
                f"TCP 서버에 연결할 수 없습니다. ({target_ip}:{self.server_port})\n{error}",
            )

    def _resolve_employee_ip(self, employee_id: str) -> tuple[Optional[str], Optional[SendResult]]:
        if self.endpoint_registry is None:
            if self.server_ip is None:
                return None, SendResult(
                    False, "로그인한 Jetson 연결 정보가 없습니다."
                )
            return self.server_ip, None
        ip_address = self.endpoint_registry.resolve(employee_id)
        if ip_address is None:
            return None, SendResult(
                False, f"{employee_id} 직원이 로그인한 Jetson을 찾을 수 없습니다."
            )
        return ip_address, None

    def send_employee_message(self, employee_id: str,
                              message_text: str) -> SendResult:
        """선택 직원에게 관리자가 입력한 메시지를 전송합니다."""
        ip_address, error = self._resolve_employee_ip(employee_id)
        if error is not None:
            return error
        result = self.send_message(
            build_employee_message(employee_id, message_text), ip_address
        )
        if result.success:
            return SendResult(True, f"{employee_id} 직원에게 메시지를 전송했습니다.")
        return result
