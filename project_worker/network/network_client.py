"""Monitoring PC와의 TCP 네트워크 통신 인프라를 담당하는 모듈입니다.

JSON 한 줄 요청/응답 전송 및 서버 연결 상태 확인 기능을 제공합니다.
"""

import json
import socket

from PyQt5.QtCore import QThread, pyqtSignal

import config


def send_json_request(payload: dict) -> dict:
    """Monitoring PC Gateway에 JSON 한 줄 요청을 보내고 응답을 받습니다."""
    timeout = config.MONITORING_REQUEST_TIMEOUT_SECONDS
    with socket.create_connection(
        (config.MONITORING_PC_IP, config.MONITORING_AUTH_PORT),
        timeout=timeout,
    ) as client:
        client.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        buffer = bytearray()
        max_response_bytes = getattr(config, "MONITORING_MAX_RESPONSE_BYTES", 65536)
        while b"\n" not in buffer and len(buffer) < max_response_bytes:
            chunk = client.recv(4096)
            if not chunk:
                break
            buffer.extend(chunk)
    if not buffer:
        raise ConnectionError("Monitoring PC에서 응답이 없습니다.")
    if b"\n" not in buffer:
        raise ConnectionError("Monitoring PC 응답이 허용된 크기를 초과했습니다.")
    return json.loads(buffer.decode("utf-8").splitlines()[0])


def check_monitoring_server_connection(timeout: float = 1.0) -> tuple[bool, str]:
    """모니터링 PC(관제 서버)와의 TCP 연결 가능 여부를 확인합니다."""
    if config.TEST_MODE:
        return True, "테스트 모드 (서버 가상 연결)"
    addr = f"{config.MONITORING_PC_IP}:{config.MONITORING_AUTH_PORT}"
    try:
        with socket.create_connection(
            (config.MONITORING_PC_IP, config.MONITORING_AUTH_PORT),
            timeout=timeout,
        ):
            return True, f"관제 서버 연결 ({addr})"
    except ConnectionRefusedError:
        return False, f"서버 연결 거부 (포트 닫힘: {addr})"
    except socket.timeout:
        return False, f"서버 응답 시간 초과 ({addr})"
    except OSError as e:
        return False, f"서버 연결 실패 ({e})"


class ServerCheckThread(QThread):
    """모니터링 PC(관제 서버) 연결 상태를 비동기로 확인하는 Thread입니다."""

    check_finished = pyqtSignal(bool, str)

    def __init__(self, timeout: float = 1.5, parent=None):
        super().__init__(parent)
        self.timeout = timeout
        self.finished.connect(self.deleteLater)

    def run(self) -> None:
        ok, msg = check_monitoring_server_connection(self.timeout)
        self.check_finished.emit(ok, msg)
