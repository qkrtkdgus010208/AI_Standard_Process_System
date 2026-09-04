"""Jetson 없이 호출 메시지를 확인하기 위한 간단한 테스트 TCP 서버입니다."""

import socket


SERVER_IP = "127.0.0.1"
SERVER_PORT = 5000


def run_mock_server() -> None:
    """연결을 반복해서 받고 수신 메시지를 콘솔에 출력합니다."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((SERVER_IP, SERVER_PORT))
        server_socket.listen()
        print(f"테스트 TCP 서버 대기 중: {SERVER_IP}:{SERVER_PORT}")
        print("종료하려면 Ctrl+C를 누르세요.")
        while True:
            client_socket, address = server_socket.accept()
            with client_socket:
                message = client_socket.recv(4096).decode("utf-8").strip()
                print(f"수신 {address}: {message}")


if __name__ == "__main__":
    try:
        run_mock_server()
    except KeyboardInterrupt:
        print("\n테스트 TCP 서버를 종료합니다.")
