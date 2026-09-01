"""USB/CSI/Mock Camera Frame을 별도 Thread에서 읽는 모듈입니다."""

import time
from typing import Optional

from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPen

import config

try:
    import cv2
except ImportError:  # TEST_MODE에서는 OpenCV가 없어도 UI를 실행할 수 있습니다.
    cv2 = None


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

    def run(self) -> None:
        """Camera Frame 읽기 Loop를 실행합니다."""
        self._running = True
        if self.backend == "mock":
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
            self.status_changed.emit(f"{self.backend.upper()} 카메라 연결", True)
            while self._running:
                success, frame = self._capture.read()
                if not success:
                    self.status_changed.emit("카메라 Frame 읽기 실패", False)
                    self.msleep(200)
                    continue
                self.frame_ready.emit(frame)
                self.msleep(max(1, int(1000 / max(1, config.CAMERA_FPS))))
        except Exception as error:
            self.status_changed.emit(f"카메라 오류: {error}", False)
        finally:
            if self._capture is not None:
                self._capture.release()
            self._capture = None

    def _open_capture(self):
        """설정에 따라 USB 또는 CSI Camera 객체를 생성합니다."""
        if self.backend == "usb":
            capture = cv2.VideoCapture(config.USB_CAMERA_INDEX)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
            capture.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
            return capture
        if self.backend == "csi":
            return cv2.VideoCapture(
                config.CSI_GSTREAMER_PIPELINE, cv2.CAP_GSTREAMER
            )
        raise ValueError(f"지원하지 않는 Camera Backend: {self.backend}")

    def _run_mock_camera(self) -> None:
        """실제 Camera 없이 움직이는 테스트 Frame을 생성합니다."""
        width, height = 960, 540
        while self._running:
            image = QImage(width, height, QImage.Format_RGB32)
            image.fill(QColor("#263746"))
            painter = QPainter(image)
            painter.setPen(QPen(QColor("#40576B"), 1))
            for x in range(0, width, 48):
                painter.drawLine(x, 0, x, height)
            for y in range(0, height, 48):
                painter.drawLine(0, y, width, y)
            scan_x = (self._mock_frame_no * 8) % width
            painter.setPen(QPen(QColor("#65A1D5"), 3))
            painter.drawLine(scan_x, 0, scan_x, height)
            painter.setPen(QColor("#D6E1EA"))
            painter.drawText(
                image.rect(), Qt.AlignCenter,
                "TEST MODE  ·  CAMERA PREVIEW\nUSB / CSI Camera 연결 전",
            )
            painter.end()
            self.frame_ready.emit(image)
            self._mock_frame_no += 1
            self.msleep(50)

    def stop(self) -> None:
        """Frame Loop를 안전하게 종료합니다."""
        self._running = False
        self.wait(2000)
