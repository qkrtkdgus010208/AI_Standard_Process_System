"""USB/CSI/Mock Camera Frame을 별도 Thread에서 읽는 모듈입니다."""

import subprocess
import time
from typing import Optional

from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPen

import config

try:
    import cv2
except ImportError:  # TEST_MODE에서는 OpenCV가 없어도 UI를 실행할 수 있습니다.
    cv2 = None

_MOCK_W, _MOCK_H = 960, 540


def _build_mock_background() -> QImage:
    """재사용 가능한 Mock 카메라 배경 이미지를 한 번만 생성합니다."""
    img = QImage(_MOCK_W, _MOCK_H, QImage.Format_RGB32)
    img.fill(QColor("#263746"))
    painter = QPainter(img)
    painter.setPen(QPen(QColor("#40576B"), 1))
    for x in range(0, _MOCK_W, 48):
        painter.drawLine(x, 0, x, _MOCK_H)
    for y in range(0, _MOCK_H, 48):
        painter.drawLine(0, y, _MOCK_W, y)
    painter.end()
    return img


class CameraThread(QThread):
    """선택한 Camera Backend에서 Frame을 읽어 UI와 AI에 전달합니다."""

    frame_ready = pyqtSignal(object)
    status_changed = pyqtSignal(str, bool)

    def __init__(self, backend: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.backend = (backend or config.CAMERA_BACKEND).lower()
        self._running = False
        self._capture = None
        self._mock_frame_no = 0
        self._is_connected = False
        self._last_frame_time = 0.0
        # Mock 배경을 한 번만 생성해 두고 스캔선만 덧그림
        self._mock_bg: Optional[QImage] = None

    def is_connected(self) -> bool:
        """카메라가 정상 연결되어 프레임을 수신 중인지 반환합니다."""
        return self._is_connected and self.isRunning() and not self.is_stalled()

    def is_stalled(self) -> bool:
        """카메라 연결 상태이나 일정 시간 프레임이 중단되었는지 확인합니다."""
        if self.backend == "mock":
            return False
        if not self._is_connected or not self.isRunning():
            return True
        return self._last_frame_time != 0.0 and (time.time() - self._last_frame_time) > 3.0

    def restart(self) -> None:
        """카메라 스레드를 안전하게 중지한 후 재시작합니다."""
        self.stop()
        self.start()

    def run(self) -> None:
        """Camera Frame 읽기 Loop를 실행합니다."""
        self._running = True
        self._is_connected = False
        self._last_frame_time = 0.0

        if self.backend == "mock":
            self._is_connected = True
            self.status_changed.emit("테스트 카메라", True)
            self._run_mock_camera()
            return

        if cv2 is None:
            self.status_changed.emit("OpenCV가 설치되지 않았습니다.", False)
            return

        try:
            self._capture = self._open_capture()
            if self._capture is None or not self._capture.isOpened():
                self.status_changed.emit("카메라를 열 수 없습니다.", False)
                return
            self._is_connected = True
            self.status_changed.emit(f"{self.backend.upper()} 카메라 연결", True)
            target_interval = 1.0 / max(1, config.CAMERA_FPS)
            while self._running:
                loop_start = time.time()
                success, frame = self._capture.read()
                if not success:
                    self._is_connected = False
                    self.status_changed.emit("카메라 연결 끊김", False)
                    break
                self._last_frame_time = time.time()

                # pass_fail_test.py 데이터셋 촬영 방향과 동일하게 상하좌우 반전
                if getattr(config, "CAMERA_FLIP", False) and frame is not None:
                    frame = cv2.flip(frame, -1)

                self.frame_ready.emit(frame)
                # 목표 FPS에서 소요된 시간을 빼고 남은 시간만 대기
                elapsed = time.time() - loop_start
                sleep_ms = int((target_interval - elapsed) * 1000)
                self.msleep(max(1, sleep_ms))
        except Exception as error:
            self._is_connected = False
            self.status_changed.emit(f"카메라 오류: {error}", False)
        finally:
            self._is_connected = False
            if self._capture is not None:
                try:
                    self._capture.release()
                except Exception:
                    pass
            self._capture = None

    def _apply_v4l2_ctl(self, device_path: Optional[str] = None) -> None:
        """C270 카메라 하드웨어 레벨 설정을 위해 v4l2-ctl을 직접 실행합니다."""
        dev = device_path or getattr(config, "CAMERA_V4L2_DEVICE", f"/dev/video{config.USB_CAMERA_INDEX}")
        auto_exp = getattr(config, "CAMERA_AUTO_EXPOSURE", 1)
        exp = getattr(config, "CAMERA_EXPOSURE", 156)
        contrast = getattr(config, "CAMERA_CONTRAST", 22)
        sharpness = getattr(config, "CAMERA_SHARPNESS", 255)
        cmd = [
            "v4l2-ctl",
            "-d", dev,
            "-c", f"auto_exposure={auto_exp}",
            "-c", f"exposure_time_absolute={exp}",
            "-c", f"contrast={contrast}",
            "-c", f"sharpness={sharpness}",
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print(f"[Camera] v4l2-ctl 설정 성공 ({dev}): auto_exposure={auto_exp}, exposure={exp}, contrast={contrast}, sharpness={sharpness}")
        except FileNotFoundError:
            print("[Camera] v4l2-ctl 명령어를 찾을 수 없습니다. (sudo apt install v4l-utils 권장) OpenCV 속성으로 설정합니다.")
        except subprocess.CalledProcessError as e:
            print(f"[Camera] v4l2-ctl 실행 실패 ({dev}): {e.stderr.strip() if e.stderr else e}")
        except Exception as e:
            print(f"[Camera] v4l2-ctl 설정 중 예외 발생: {e}")

    def _apply_camera_settings(self, capture) -> None:
        """pass_fail_test.py와 동일한 카메라 노출, 대비, 선명도 설정을 적용합니다."""
        auto_exp = getattr(config, "CAMERA_AUTO_EXPOSURE", 1)
        # Windows DSHOW는 0.25, Linux V4L2는 1이 수동(Manual) 노출 모드
        if not capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, auto_exp):
            capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)

        exp_val = getattr(config, "CAMERA_EXPOSURE", 156)
        # Windows DSHOW의 2의 거듭제곱 값(e.g. -6 = 1/64초)이 입력된 경우
        # Linux V4L2(100us 단위)로 자동 변환: 2^-6 * 10000 ≈ 156
        if exp_val < 0:
            exp_val = max(1, int(round((2 ** exp_val) * 10000)))

        capture.set(cv2.CAP_PROP_EXPOSURE, exp_val)
        capture.set(cv2.CAP_PROP_CONTRAST, getattr(config, "CAMERA_CONTRAST", 22))
        capture.set(cv2.CAP_PROP_SHARPNESS, getattr(config, "CAMERA_SHARPNESS", 255))

    def _open_capture(self):
        """설정에 따라 USB 또는 CSI Camera 객체를 생성하고 pass_fail_test 설정을 적용합니다."""
        if self.backend == "usb":
            # 1. C270 하드웨어 직접 v4l2-ctl 제어 (카메라 오픈 전 적용)
            self._apply_v4l2_ctl()

            capture = cv2.VideoCapture(config.USB_CAMERA_INDEX)
            if not capture.isOpened():
                return capture

            capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
            capture.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)

            # pass_fail_test.py와 동일한 카메라 초기화 시퀀스
            for _ in range(30):
                capture.read()

            self._apply_camera_settings(capture)
            self._apply_v4l2_ctl()

            for _ in range(10):
                capture.read()

            self._apply_camera_settings(capture)
            self._apply_v4l2_ctl()

            return capture
        if self.backend == "csi":
            return cv2.VideoCapture(config.CSI_GSTREAMER_PIPELINE, cv2.CAP_GSTREAMER)
        raise ValueError(f"지원하지 않는 Camera Backend: {self.backend}")

    def _run_mock_camera(self) -> None:
        """배경을 한 번만 생성하고 스캔선만 매 프레임 갱신하여 CPU를 절약합니다."""
        if self._mock_bg is None:
            self._mock_bg = _build_mock_background()

        text_pen = QColor("#D6E1EA")
        scan_pen = QPen(QColor("#65A1D5"), 3)

        while self._running:
            # 배경 복사 후 스캔선과 텍스트만 덧그림
            frame = self._mock_bg.copy()
            painter = QPainter(frame)
            scan_x = (self._mock_frame_no * 8) % _MOCK_W
            painter.setPen(scan_pen)
            painter.drawLine(scan_x, 0, scan_x, _MOCK_H)
            painter.setPen(text_pen)
            painter.drawText(
                frame.rect(), Qt.AlignCenter,
                "TEST MODE  ·  CAMERA PREVIEW\nUSB / CSI Camera 연결 전",
            )
            painter.end()
            self.frame_ready.emit(frame)
            self._mock_frame_no += 1
            self.msleep(50)

    def stop(self) -> None:
        """Frame Loop를 안전하게 종료합니다."""
        self._running = False
        if self.isRunning():
            self.wait(2000)
