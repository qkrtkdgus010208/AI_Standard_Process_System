"""Monitoring PC 호출 메시지를 별도 Thread에서 수신하는 TCP 서버입니다."""

import socket
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

import config


class TcpServerThread(QThread):
    """여러 TCP 연결을 순차 수락하고 줄 단위 메시지를 UI에 전달합니다."""

    message_received = pyqtSignal(str, str)
    status_changed = pyqtSignal(str, bool)

    def __init__(self, host: Optional[str] = None,
                 port: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.host = host or config.TCP_SERVER_HOST
        self.port = port or config.TCP_SERVER_PORT
        self._running = False
        self._server_socket = None

    def run(self) -> None:
        """TCP Server를 열고 Monitoring PC 연결을 기다립니다."""
        if not config.TCP_ENABLED:
            self.status_changed.emit("TCP 서버 비활성", False)
            return
        self._running = True
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                self._server_socket = server_socket
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.settimeout(0.5)
                server_socket.bind((self.host, self.port))
                server_socket.listen(5)
                self.port = server_socket.getsockname()[1]
                self.status_changed.emit(f"TCP 대기: {self.host}:{self.port}", True)
                while self._running:
                    try:
                        client_socket, address = server_socket.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    self._receive_client(client_socket, address[0])
        except OSError as error:
            self.status_changed.emit(f"TCP 서버 오류: {error}", False)
        finally:
            self._server_socket = None

    def _receive_client(self, client_socket: socket.socket, address: str) -> None:
        """한 Client가 보낸 모든 줄 단위 메시지를 수신합니다."""
        with client_socket:
            client_socket.settimeout(config.TCP_CLIENT_TIMEOUT_SECONDS)
            chunks = []
            while self._running:
                try:
                    data = client_socket.recv(4096)
                except socket.timeout:
                    break
                if not data:
                    break
                chunks.append(data)
            text = b"".join(chunks).decode("utf-8", errors="replace")
            for line in text.splitlines():
                if line.strip():
                    self.message_received.emit(line.strip(), address)

    def stop(self) -> None:
        """accept 대기를 해제하고 TCP Server를 종료합니다."""
        self._running = False
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
        self.wait(2500)
