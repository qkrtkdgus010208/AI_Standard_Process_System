"""Jetson 작업자용 메인 PyQt 화면입니다."""

from datetime import datetime
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

import config
from services.auth_manager import WorkerSession
from devices.ai_judge import AiInferenceThread, JudgeResult
from devices.camera_manager import CameraThread
from ui.dialogs.ai_result_dialog import AiResultDialog
from services.product_service import ProductInfo, ProductFetchThread, StepGuideFetchThread
from network.protocol import decode_message_text, parse_message
from network.server_monitor import ServerMonitor
from services.state_reporter import MonitoringEventThread
from devices.stm_controller import StmController
from network.tcp_server import TcpServerThread
from devices.uart_manager import UartReceiverThread
from services.work_state import WorkStateController

try:
    import cv2
except ImportError:
    cv2 = None

# ── 상태 표시 색상 및 텍스트 상수 ──────────────────────────────────────────
_STATE_TEXT = {
    "idle": "작업 대기", "running": "작업 진행 중",
    "paused": "일시정지", "complete": "작업 완료",
}
_STATE_COLOR = {
    "idle":     ("#5F6D7A", "#F1F4F6"),
    "running":  ("#2F7651", "#EAF5EE"),
    "paused":   ("#8A641F", "#FFF6DF"),
    "complete": ("#315E91", "#EAF1F8"),
}
_RESULT_STYLE = {
    "pass":    ("PASS",    "#2F7651", "#EAF5EE"),
    "fail":    ("FAIL",    "#AE5050", "#FCEEEE"),
}
_RESULT_DEFAULT = ("판정 대기", "#6F7B89", "#F4F6F8")
_LOG_COLORS = {
    "success": "#2F7651", "warning": "#8A641F",
    "error":   "#AE5050", "info":    "#526170",
}
_LOG_DEFAULT_COLOR = "#526170"

# STEP 기준 이미지 패널 스타일 (텍스트 모드: 16px 패딩+큰 폰트 / 이미지 모드: 0px 패딩으로 패널 가득 채움)
_GUIDE_TEXT_STYLE = (
    "color:#3A4757; background:#F4F6F8; border:1px solid #DDE3EA; border-radius:7px; "
    "font-size:20px; font-weight:600; padding:16px;"
)
_GUIDE_IMAGE_STYLE = (
    "background:#1E293B; border:1px solid #BFC9D3; border-radius:7px; padding:0px;"
)


class WorkerWindow(QMainWindow):
    """Camera 영상과 공정 제어 상태를 표시하는 작업자 화면입니다."""

    logout_requested = pyqtSignal()

    def __init__(self, session: WorkerSession):
        super().__init__()
        self.session = session
        self.setWindowTitle("공정 모니터링 · 작업자 프로그램")
        self.setMinimumSize(1120, 720)
        self.resize(1360, 1000)

        # ── 상태 플래그 ──
        self._latest_frame = None
        self._ai_busy = False
        self._services_started = False
        self._saved_work_restored = False
        self._is_terminating = False

        # ── 제품 목록 관련 ──
        self.products: list[ProductInfo] = []
        self._current_product: Optional[ProductInfo] = None
        self.product_fetch_thread: Optional[ProductFetchThread] = None
        self._guide_fetch_thread: Optional[StepGuideFetchThread] = None
        self._requested_guide_key = None
        self._displayed_guide_key = None
        self._guide_pixmap_cache: dict[tuple[str, int], QPixmap] = {}
        self.message_popup: Optional[QMessageBox] = None

        # ── 서비스 스레드 ──
        self.work_controller = WorkStateController()
        self.camera_thread = CameraThread()
        self.ai_thread = AiInferenceThread()
        self.uart_thread = UartReceiverThread()
        self.tcp_thread = TcpServerThread()
        self.monitoring_event_thread = MonitoringEventThread(session=session, parent=self)
        self.monitoring_event_thread.status_changed.connect(self._on_monitoring_event_status)
        self.monitoring_event_thread.start()

        # ── STM32 명령 컨트롤러 ──
        self.stm = StmController(self.uart_thread, self.add_log)

        # ── 서버 연결 감시 ──
        self.server_monitor = ServerMonitor(
            parent=self,
            on_disconnected=self.handle_server_disconnected,
        )

        self._create_ui()
        self._connect_signals()
        # UART 명령 디스패치 테이블 — handle_uart_message 호출마다 재생성하지 않도록 캐싱
        self._uart_handlers = {
            "CHECK":  self._on_uart_check,
            "PAUSE":  self._on_uart_pause,
            "RESUME": self._on_uart_resume,
            "RESET":  self._on_uart_reset,
            "START":  self._on_uart_start,
            "PASS":   self._on_uart_pass,
            "FAIL":   self._on_uart_fail,
        }
        # UI가 먼저 그려진 뒤 서비스 시작
        QTimer.singleShot(0, self._start_all)

    # ── UI 생성 헬퍼 ─────────────────────────────────────────────────────────

    @staticmethod
    def _make_card(title: str, subtitle: str = ""):
        """공통 카드 Frame과 내부 Layout을 생성합니다."""
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("mutedText")
            sub.setStyleSheet("font-size:11px;")
            layout.addWidget(sub)
        return card, layout

    @staticmethod
    def _field(label_text: str, input_widget: QWidget) -> QWidget:
        """라벨과 입력 위젯을 세로로 묶습니다."""
        label = QLabel(label_text)
        label.setObjectName("smallLabel")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(label)
        layout.addWidget(input_widget)
        container = QWidget()
        container.setLayout(layout)
        return container

    def _make_status_item(self, label_text: str):
        """가로 장치 상태 카드에 들어갈 장치명/상태 묶음을 만듭니다."""
        name_label = QLabel(label_text)
        name_label.setObjectName("smallLabel")
        status_label = QLabel("● 대기")
        status_label.setStyleSheet("color:#7B8794;")
        item_layout = QVBoxLayout()
        item_layout.setContentsMargins(8, 0, 8, 0)
        item_layout.setSpacing(2)
        item_layout.addWidget(name_label)
        item_layout.addWidget(status_label)
        item = QWidget()
        item.setLayout(item_layout)
        return item, status_label

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _create_ui(self) -> None:
        """작업 설정, 영상, STEP 제어, 장치 상태 화면을 구성합니다."""
        # ── 상단 바 ──
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(68)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(26, 0, 26, 0)
        logo = QLabel("FM")
        logo.setFixedSize(38, 38)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("color:#FFFFFF; background:#315E91; border-radius:8px; font-weight:900;")
        app_name = QLabel("공정 모니터링  ·  작업자")
        app_name.setStyleSheet("font-size:14px; font-weight:700; color:#263442;")
        self.clock_label = QLabel("")
        self.clock_label.setStyleSheet("color:#5F6D7A; font-weight:600;")
        user_label = QLabel(f"●  {self.session.name} · {self.session.employee_id}")
        user_label.setStyleSheet(
            "color:#445362;background:#F6F8FA;border:1px solid #D7DFE7;"
            "border-radius:14px;padding:6px 11px;"
        )
        logout_button = QPushButton("로그아웃")
        logout_button.setFixedWidth(86)
        logout_button.clicked.connect(self.on_logout_clicked)
        top_layout.addWidget(logo)
        top_layout.addWidget(app_name)
        top_layout.addStretch()
        top_layout.addWidget(user_label)
        top_layout.addSpacing(12)
        top_layout.addWidget(logout_button)
        top_layout.addSpacing(12)
        top_layout.addWidget(self.clock_label)

        # ── 호출 배너 ──
        self.call_banner = QFrame()
        self.call_banner.setObjectName("callBanner")
        self.call_banner.setVisible(False)
        call_layout = QHBoxLayout(self.call_banner)
        call_layout.setContentsMargins(16, 10, 12, 10)
        self.call_message_label = QLabel("관리자 호출 메시지")
        self.call_message_label.setStyleSheet("color:#74531A; font-weight:700;")
        dismiss_button = QPushButton("확인")
        dismiss_button.setFixedWidth(72)
        dismiss_button.clicked.connect(lambda: self.call_banner.setVisible(False))
        call_layout.addWidget(self.call_message_label)
        call_layout.addStretch()
        call_layout.addWidget(dismiss_button)

        # ── 작업 정보 카드 ──
        title = QLabel("조립 작업")
        title.setObjectName("pageTitle")
        subtitle = QLabel("카메라 영상과 판정 결과를 확인하며 STEP별 작업을 진행하세요.")
        subtitle.setObjectName("subtitle")

        setup_card, setup_layout = self._make_card(
            "작업 정보", "모니터링 PC SQLite DB에 등록된 제품을 선택하면 제품번호와 전체 STEP이 자동 지정됩니다."
        )
        setup_grid = QGridLayout()
        setup_grid.setContentsMargins(0, 2, 0, 0)
        setup_grid.setHorizontalSpacing(12)

        self.employee_id_display = QLineEdit(self.session.employee_id)
        self.employee_id_display.setReadOnly(True)
        self.employee_name_display = QLineEdit(self.session.name)
        self.employee_name_display.setReadOnly(True)
        self.product_name_combo = QComboBox()
        self.product_name_combo.setMinimumWidth(180)
        self.product_name_combo.currentIndexChanged.connect(self._on_product_changed)
        self.product_id_display = QLineEdit()
        self.product_id_display.setReadOnly(True)
        self.product_id_display.setPlaceholderText("제품번호")
        self.total_steps_display = QLineEdit()
        self.total_steps_display.setReadOnly(True)
        self.total_steps_display.setPlaceholderText("전체 STEP")

        setup_grid.addWidget(self._field("로그인 직원번호", self.employee_id_display), 0, 0)
        setup_grid.addWidget(self._field("작업자 이름", self.employee_name_display), 0, 1)
        setup_grid.addWidget(self._field("제품명 선택", self.product_name_combo), 0, 2)
        setup_grid.addWidget(self._field("제품번호", self.product_id_display), 0, 3)
        setup_grid.addWidget(self._field("전체 STEP", self.total_steps_display), 0, 4)
        self.refresh_button = QPushButton("제품 새로고침")
        self.refresh_button.clicked.connect(self.fetch_products)
        setup_grid.addWidget(self.refresh_button, 0, 5, alignment=Qt.AlignBottom)
        setup_grid.setColumnStretch(2, 2)
        setup_grid.setColumnStretch(3, 1)
        setup_grid.setColumnStretch(4, 1)
        setup_layout.addLayout(setup_grid)

        # ── 카메라 카드 ──
        camera_card, camera_layout = self._make_card(
            "카메라 · STEP 기준 이미지", "실제 조립 상태와 관리자가 등록한 정상 예시를 비교하세요."
        )
        image_row = QHBoxLayout()
        image_row.setSpacing(10)
        camera_panel = QVBoxLayout()
        camera_title = QLabel("현재 카메라")
        camera_title.setObjectName("smallLabel")
        self.camera_view = QLabel("카메라 연결 대기 중")
        self.camera_view.setAlignment(Qt.AlignCenter)
        self.camera_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.camera_view.setMinimumSize(360, 300)
        self.camera_view.setScaledContents(True)
        self.camera_view.setStyleSheet(
            "color:#C7D2DC; background:#1E293B; border:1px solid #BFC9D3; border-radius:7px;"
        )
        camera_panel.addWidget(camera_title)
        camera_panel.addWidget(self.camera_view, 1)

        guide_panel = QVBoxLayout()
        self.guide_title_label = QLabel("STEP 기준 이미지")
        self.guide_title_label.setObjectName("smallLabel")
        self.step_guide_view = QLabel("작업을 시작하면\n기준 이미지가 표시됩니다.")
        self.step_guide_view.setAlignment(Qt.AlignCenter)
        self.step_guide_view.setWordWrap(True)
        self.step_guide_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.step_guide_view.setMinimumSize(300, 300)
        self.step_guide_view.setStyleSheet(_GUIDE_TEXT_STYLE)
        guide_panel.addWidget(self.guide_title_label)
        guide_panel.addWidget(self.step_guide_view, 1)
        image_row.addLayout(camera_panel, 1)
        image_row.addLayout(guide_panel, 1)
        camera_layout.addLayout(image_row, 1)

        # ── 작업 상태 카드 ──
        progress_card, progress_layout = self._make_card("현재 작업 상태")
        self.state_badge = QLabel("작업 대기")
        self.state_badge.setAlignment(Qt.AlignCenter)
        self.state_badge.setMinimumHeight(34)
        self.current_step_label = QLabel("STEP 0 / 1")
        self.current_step_label.setAlignment(Qt.AlignCenter)
        self.current_step_label.setStyleSheet(
            "color:#244A75; font-size:28px; font-weight:700; margin:8px;"
        )
        self.work_progress = QProgressBar()
        self.work_progress.setRange(0, 1)
        self.work_progress.setValue(0)
        self.result_label = QLabel("판정 대기")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setMinimumHeight(58)
        self.result_label.setStyleSheet(
            "color:#6F7B89; background:#F4F6F8; border:1px solid #DDE3EA; "
            "border-radius:7px; font-size:20px; font-weight:700;"
        )
        progress_layout.addWidget(self.state_badge)
        summary_row = QHBoxLayout()
        summary_row.setSpacing(8)
        summary_row.addWidget(self.current_step_label, 1)
        summary_row.addWidget(self.result_label, 1)
        progress_layout.addLayout(summary_row)
        progress_layout.addWidget(self.work_progress)

        # ── 제어 버튼 ──
        self.start_button = QPushButton("작업 시작")
        self.start_button.setObjectName("primaryButton")
        self.pause_button = QPushButton("일시정지")
        self.pause_button.setObjectName("warningButton")
        self.resume_button = QPushButton("작업 재개")
        self.defect_button = QPushButton("불량 등록")
        self.defect_button.setObjectName("dangerButton")
        self.defect_button.setEnabled(False)
        self.start_button.clicked.connect(self.on_start_work_clicked)
        self.pause_button.clicked.connect(self.on_pause_clicked)
        self.resume_button.clicked.connect(self.on_resume_clicked)
        self.defect_button.clicked.connect(self.on_defect_clicked)
        control_grid = QGridLayout()
        control_grid.addWidget(self.start_button, 0, 0)
        control_grid.addWidget(self.pause_button, 0, 1)
        control_grid.addWidget(self.resume_button, 1, 0)
        control_grid.addWidget(self.defect_button, 1, 1)
        progress_layout.addLayout(control_grid)

        self.ai_button = QPushButton("AI 판정 실행")
        self.ai_button.clicked.connect(self.request_ai_judgement)
        progress_layout.addWidget(self.ai_button)

        if config.TEST_MODE:
            test_row = QHBoxLayout()
            pass_button = QPushButton("PASS 테스트")
            pass_button.setObjectName("successButton")
            fail_button = QPushButton("FAIL 테스트")
            fail_button.setObjectName("dangerButton")
            pass_button.clicked.connect(lambda: self.uart_thread.simulate_receive("PASS"))
            fail_button.clicked.connect(lambda: self.uart_thread.simulate_receive("FAIL"))
            test_row.addWidget(pass_button)
            test_row.addWidget(fail_button)
            progress_layout.addLayout(test_row)

        # ── 장치 상태 카드 ──
        status_card = QFrame()
        status_card.setObjectName("card")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(18, 12, 18, 12)
        status_title = QLabel("장치 연결 상태")
        status_title.setObjectName("sectionTitle")
        status_layout.addWidget(status_title)
        status_layout.addSpacing(18)
        camera_item, self.camera_status = self._make_status_item("Camera")
        ai_item, self.ai_status = self._make_status_item("AI")
        uart_item, self.uart_status = self._make_status_item("UART")
        tcp_item, self.tcp_status = self._make_status_item("TCP Server")
        for item in (camera_item, ai_item, uart_item, tcp_item):
            status_layout.addWidget(item, 1)
        self.device_refresh_button = QPushButton("장치 새로고침")
        self.device_refresh_button.setCursor(Qt.PointingHandCursor)
        self.device_refresh_button.setToolTip("장치 연결 상태를 확인하고 끊어진 장치의 재연결을 시도합니다.")
        status_layout.addWidget(self.device_refresh_button)

        # ── 로그 카드 ──
        log_card, log_layout = self._make_card("시스템 기록")
        self.log_list = QListWidget()
        self.log_list.setAlternatingRowColors(True)
        self.log_list.setMaximumHeight(130)
        log_layout.addWidget(self.log_list)

        # ── 레이아웃 조립 ──
        main_row = QHBoxLayout()
        main_row.setSpacing(14)
        main_row.addWidget(camera_card, 2)
        progress_card.setMinimumWidth(390)
        main_row.addWidget(progress_card, 1)

        content = QVBoxLayout()
        content.setContentsMargins(24, 20, 24, 24)
        content.setSpacing(12)
        content.addWidget(self.call_banner)
        content.addWidget(title)
        content.addWidget(subtitle)
        content.addWidget(setup_card)
        content.addLayout(main_row, 1)
        content.addWidget(status_card)
        content.addWidget(log_card)

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(top_bar)
        root_layout.addLayout(content)
        root = QWidget()
        root.setLayout(root_layout)
        self.setCentralWidget(root)

        # 시계
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

    # ── 시그널 연결 ──────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        """Thread와 상태 Controller 신호를 UI Slot에 연결합니다."""
        self.work_controller.state_changed.connect(self.update_work_state)
        self.work_controller.state_changed.connect(self.monitoring_event_thread.enqueue_state)
        self.work_controller.log_created.connect(self.add_log)

        self.camera_thread.frame_ready.connect(self.update_camera_frame)
        self.camera_thread.status_changed.connect(
            lambda text, ok: self.update_device_status(self.camera_status, text, ok)
        )
        self.ai_thread.judgement_ready.connect(self.handle_ai_result)
        self.ai_thread.status_changed.connect(
            lambda text, ok: self.update_device_status(self.ai_status, text, ok)
        )
        self.uart_thread.message_received.connect(self.handle_uart_message)
        self.uart_thread.status_changed.connect(
            lambda text, ok: self.update_device_status(self.uart_status, text, ok)
        )
        self.tcp_thread.message_received.connect(self.handle_tcp_message)
        self.tcp_thread.status_changed.connect(
            lambda text, ok: self.update_device_status(self.tcp_status, text, ok)
        )
        self.device_refresh_button.clicked.connect(self.refresh_device_connections)

    # ── 초기화 및 서비스 시작 ────────────────────────────────────────────────

    def _start_all(self) -> None:
        """서비스 스레드 시작과 제품 목록 조회를 한 번에 처리합니다."""
        if self._services_started:
            return
        self._services_started = True
        for thread in (self.camera_thread, self.ai_thread, self.uart_thread, self.tcp_thread):
            thread.start()
        self.add_log("info", "작업자 프로그램 서비스를 시작했습니다.")
        self.server_monitor.start()
        self.fetch_products()

    # ── 제품 목록 관련 ───────────────────────────────────────────────────────

    def fetch_products(self) -> None:
        """모니터링 PC의 products 테이블로부터 제품 목록을 비동기 조회합니다."""
        if self.product_fetch_thread is not None and self.product_fetch_thread.isRunning():
            return
        self._displayed_guide_key = None
        self._guide_pixmap_cache.clear()
        self.product_fetch_thread = ProductFetchThread(token=self.session.token, parent=self)
        self.product_fetch_thread.products_fetched.connect(self._on_products_fetched)
        self.product_fetch_thread.finished.connect(self._clear_product_fetch_thread)
        self.product_fetch_thread.start()

    def _clear_product_fetch_thread(self) -> None:
        self.product_fetch_thread = None

    def _on_products_fetched(self, products: list, success: bool, message: str) -> None:
        """가져온 제품 목록을 드롭다운에 채우고, 이전 작업이 남아있으면 복원합니다."""
        self.products = products
        self.product_name_combo.blockSignals(True)
        self.product_name_combo.clear()
        for prod in self.products:
            self.product_name_combo.addItem(f"{prod.product_name} ({prod.product_id})", prod)
        self.product_name_combo.blockSignals(False)

        # 로그인 후 최초 1회만 이전 작업 복원 시도
        if not self._saved_work_restored:
            self._saved_work_restored = True
            if self._try_restore_previous_work():
                self.add_log("info" if success else "warning", message)
                return
            else:
                self.stm.send_standby()

        if self.products:
            self._on_product_changed(self.product_name_combo.currentIndex())
        else:
            self._current_product = None
            self.product_id_display.clear()
            self.total_steps_display.clear()
        self.add_log("info" if success else "warning", message)
        if not success and any(kw in message for kw in ("연결", "네트워크", "Connection")):
            self.handle_server_disconnected("제품 목록 조회 중 서버 연결이 끊겼습니다.")

    def _try_restore_previous_work(self) -> bool:
        """서버 로그인 시 수신된 이전 작업 내용이 남아있는 경우 복원합니다."""
        saved_state = self.session.saved_state
        if not saved_state:
            return False
        product_id = saved_state.get("product_id")
        if not product_id:
            return False

        # 제품 목록에서 일치 항목 탐색
        target_product: Optional[ProductInfo] = None
        target_index = -1
        for idx, prod in enumerate(self.products):
            if prod.product_id == product_id:
                target_product = prod
                target_index = idx
                break

        # 목록에 없으면 saved_state에서 즉석 생성
        if target_product is None:
            target_product = ProductInfo(
                product_id=product_id,
                product_name=str(saved_state.get("product_name") or product_id),
                total_steps=max(1, int(saved_state.get("total_steps") or 1)),
            )
            self.products.append(target_product)
            self.product_name_combo.addItem(
                f"{target_product.product_name} ({target_product.product_id})",
                target_product,
            )
            target_index = self.product_name_combo.count() - 1

        self.product_name_combo.blockSignals(True)
        self.product_name_combo.setCurrentIndex(target_index)
        self.product_name_combo.blockSignals(False)

        self._current_product = target_product
        self.product_id_display.setText(target_product.product_id)
        total_steps = max(1, int(saved_state.get("total_steps") or target_product.total_steps))
        self.total_steps_display.setText(f"{total_steps} 단계")

        self.work_controller.restore_state(
            employee_id=self.session.employee_id,
            employee_name=self.session.name,
            saved_state=saved_state,
        )

        current_step = saved_state.get("current_step", 1)
        state_str = "작업 진행 중" if saved_state.get("state") == "running" else "일시정지"
        self.add_log(
            "success",
            f"서버 이전 작업 복원 완료: {target_product.product_name} "
            f"(STEP {current_step}/{total_steps}) - 작업을 계속 진행합니다.",
        )

        # 서버에서 복원된 작업 상황(STEP, 일시정지 상태)을 STM32로 전송하여 하드웨어 동기화
        self.stm.send_step_restore(current_step, saved_state.get("state", "running"))

        # AI 판정기에 복원된 제품 레시피 동기화
        if hasattr(self, "ai_thread") and self.ai_thread and target_product:
            recipe_name = self.ai_thread.set_product(target_product.product_name, target_product.product_id)
            if recipe_name:
                self.add_log("info", f"복원 제품 레시피 적용: {recipe_name}")

        QMessageBox.information(
            self,
            "이전 작업 복원",
            f"서버에 이전에 작업하던 내용이 남아있어 자동으로 복원했습니다.\n\n"
            f"· 제품: {target_product.product_name} ({target_product.product_id})\n"
            f"· 복원 단계: STEP {current_step} / {total_steps}\n"
            f"· 작업 상태: {state_str}\n\n"
            f"이전 작업 위치부터 계속 이어서 진행할 수 있습니다.",
        )
        return True

    def _on_product_changed(self, index: int) -> None:
        """드롭다운에서 제품 선택 시 제품번호와 전체 STEP을 표시하고 작업 정보를 갱신합니다."""
        if 0 <= index < len(self.products):
            product = self.products[index]
        else:
            product = self.product_name_combo.currentData()
            if product is None:
                return
        self._current_product = product
        self._guide_pixmap_cache.clear()
        self.product_id_display.setText(product.product_id)
        self.total_steps_display.setText(f"{product.total_steps} 단계")
        self._apply_work_setup()
        self._clear_step_guide("작업을 시작하면\n기준 이미지가 표시됩니다.")

        # AI 판정기에 선택된 제품 레시피 동기화
        if hasattr(self, "ai_thread") and self.ai_thread:
            recipe_name = self.ai_thread.set_product(product.product_name, product.product_id)
            if recipe_name:
                self.add_log("info", f"제품 선택: {product.product_name} ({product.product_id}) → AI 레시피: {recipe_name}")

    def _apply_work_setup(self) -> None:
        """선택된 제품 정보를 Controller에 적용합니다."""
        if self._current_product is None:
            return
        self.work_controller.configure(
            self.session.employee_id, self.session.name,
            self._current_product.product_id, self._current_product.product_name,
            self._current_product.total_steps,
        )

    def _set_guide_text(self, message: str) -> None:
        """기준 이미지 패널을 텍스트 모드로 전환하고 메시지를 표시합니다."""
        self.step_guide_view.setScaledContents(False)
        self.step_guide_view.setStyleSheet(_GUIDE_TEXT_STYLE)
        self.step_guide_view.clear()
        self.step_guide_view.setText(message)

    def _clear_step_guide(self, message: str = "작업을 시작하면\n기준 이미지가 표시됩니다.") -> None:
        """기준 이미지를 지우고 대기 안내 문구로 초기화합니다."""
        self._requested_guide_key = None
        if self._displayed_guide_key is None and self.step_guide_view.text() == message:
            return
        self._displayed_guide_key = None
        self.guide_title_label.setText("STEP 기준 이미지")
        self._set_guide_text(message)

    def _request_step_guide(self, product_id: str, step_no: int) -> None:
        """요청된 제품·STEP 기준 이미지를 캐시 또는 비동기 네트워크로 가져옵니다."""
        if self._is_terminating or not product_id or int(step_no) < 1:
            return
        key = (str(product_id), int(step_no))
        self._requested_guide_key = key
        if self._displayed_guide_key == key:
            return

        cached_pixmap = self._guide_pixmap_cache.get(key)
        if cached_pixmap is not None and not cached_pixmap.isNull():
            self._displayed_guide_key = key
            self.guide_title_label.setText(f"STEP {step_no} 기준 이미지")
            self.step_guide_view.setStyleSheet(_GUIDE_IMAGE_STYLE)
            self.step_guide_view.setScaledContents(True)
            self.step_guide_view.setPixmap(cached_pixmap)
            return

        if self._guide_fetch_thread is not None and self._guide_fetch_thread.isRunning():
            return
        self.guide_title_label.setText(f"STEP {step_no} 기준 이미지")
        self._set_guide_text("기준 이미지 불러오는 중…")
        thread = StepGuideFetchThread(
            self.session.token, key[0], key[1], parent=self
        )
        self._guide_fetch_thread = thread
        thread.guide_fetched.connect(self._on_step_guide_fetched)
        thread.finished.connect(self._on_step_guide_fetch_finished)
        thread.start()

    def _on_step_guide_fetched(self, product_id: str, step_no: int,
                               image_data, success: bool, message: str) -> None:
        key = (product_id, int(step_no))
        if key != self._requested_guide_key:
            return
        self._displayed_guide_key = key
        self.guide_title_label.setText(f"STEP {step_no} 기준 이미지")
        if not success:
            self._set_guide_text("기준 이미지를\n불러오지 못했습니다.")
            self.add_log("warning", message)
            return
        if image_data is None:
            self._set_guide_text("등록된 기준 이미지가\n없습니다.")
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(image_data):
            self._set_guide_text("기준 이미지가\n손상되었습니다.")
            self.add_log("warning", "STEP 기준 이미지 데이터를 표시할 수 없습니다.")
            return
        self._guide_pixmap_cache[key] = pixmap
        self.step_guide_view.setStyleSheet(_GUIDE_IMAGE_STYLE)
        self.step_guide_view.setScaledContents(True)
        self.step_guide_view.setPixmap(pixmap)

    def _on_step_guide_fetch_finished(self) -> None:
        self._guide_fetch_thread = None
        if (not self._is_terminating
                and self._requested_guide_key is not None
                and self._requested_guide_key != self._displayed_guide_key):
            product_id, step_no = self._requested_guide_key
            self._request_step_guide(product_id, step_no)

    # ── 작업 상태 UI 갱신 ────────────────────────────────────────────────────

    def update_work_state(self, state: dict) -> None:
        """Controller 상태를 STEP, Progress, Button에 반영합니다."""
        state_name = state["state"]
        fg, bg = _STATE_COLOR.get(state_name, _STATE_COLOR["idle"])
        self.state_badge.setText(f"●  {_STATE_TEXT.get(state_name, state_name)}")
        self.state_badge.setStyleSheet(
            f"color:{fg}; background:{bg}; border-radius:6px; font-weight:700;"
        )
        self.current_step_label.setText(
            f"STEP {state['current_step']} / {state['total_steps']}"
        )

        # 작업 시작 후 진행 중(running, paused)인 STEP에서만 기준 이미지를 표시합니다.
        # 공정 완료(complete), 불량 등록(defect), 대기(idle) 등 작업이 종료/대기 상태이면 이미지를 숨깁니다.
        is_active_work = (
            state_name in ("running", "paused")
            and int(state.get("current_step") or 0) >= 1
            and state.get("last_result") != "defect"
            and state.get("event") not in ("manual_defect", "complete")
        )
        if is_active_work:
            self._request_step_guide(
                str(state.get("product_id") or ""), int(state["current_step"])
            )
        else:
            if state_name == "complete" or state.get("event") == "complete" or state.get("detail") == "공정 완료 후 초기화":
                self._clear_step_guide("공정이 완료되었습니다.\n작업을 시작하면 기준 이미지가 표시됩니다.")
            elif state.get("last_result") == "defect" or state.get("event") == "manual_defect" or state.get("detail") == "불량 등록 후 초기화":
                self._clear_step_guide("불량 등록으로 작업이 종료되었습니다.\n작업을 시작하면 기준 이미지가 표시됩니다.")
            else:
                self._clear_step_guide("작업을 시작하면\n기준 이미지가 표시됩니다.")

        self.work_progress.setRange(0, state["total_steps"])
        if state_name == "complete":
            completed = state["total_steps"]
        elif state["current_step"] == 0:
            completed = 0
        else:
            completed = state["current_step"] - 1
        self.work_progress.setValue(max(0, completed))
        self._update_result_display(state["last_result"])

        is_idle = state_name in ("idle", "complete")
        is_running = state_name == "running"
        self.product_name_combo.setEnabled(is_idle)
        self.refresh_button.setEnabled(is_idle)
        self.start_button.setEnabled(is_idle and self._current_product is not None)
        self.pause_button.setEnabled(is_running)
        self.resume_button.setEnabled(state_name == "paused")
        self.defect_button.setEnabled(is_running)
        self.ai_button.setEnabled(is_running and not self._ai_busy)

    def _update_result_display(self, result: str, confidence: Optional[float] = None) -> None:
        """판정 상태를 색상과 텍스트로 표시합니다."""
        text, fg, bg = _RESULT_STYLE.get(result, _RESULT_DEFAULT)
        if confidence is not None:
            text += f"  ·  {confidence * 100:.1f}%"
        self.result_label.setText(text)
        self.result_label.setStyleSheet(
            f"color:{fg}; background:{bg}; border:1px solid #DDE3EA; "
            "border-radius:7px; font-size:20px; font-weight:700;"
        )

    # ── 카메라 ───────────────────────────────────────────────────────────────

    def update_camera_frame(self, frame) -> None:
        """Camera Thread의 Frame을 패널에 빈틈없이 꽉 채워 표시하고 최신 Frame을 보관합니다."""
        self._latest_frame = frame
        if frame is None:
            return
        if isinstance(frame, QImage):
            self.camera_view.setPixmap(QPixmap.fromImage(frame))
        elif cv2 is not None and hasattr(frame, "shape"):
            fh, fw = frame.shape[:2]
            qimg = QImage(frame.data, fw, fh, fw * 3, QImage.Format_BGR888)
            self.camera_view.setPixmap(QPixmap.fromImage(qimg))

    # ── 작업 제어 버튼 핸들러 ────────────────────────────────────────────────

    def on_start_work_clicked(self) -> None:
        """'작업 시작' 버튼 클릭 시 공정을 시작하고 STM32로 'S' 명령을 전송합니다."""
        self.work_controller.start()
        if self.work_controller.snapshot.state == "running":
            self.stm.send_start()

    def on_pause_clicked(self) -> None:
        """'일시정지' 버튼 클릭 시 작업을 일시정지하고 STM32로 'U' 명령을 전송합니다."""
        self.work_controller.pause()
        if self.work_controller.snapshot.state == "paused":
            self.stm.send_pause()

    def on_resume_clicked(self) -> None:
        """'작업 재개' 버튼 클릭 시 작업을 재개하고 STM32로 'M' 명령을 전송합니다."""
        self.work_controller.resume()
        if self.work_controller.snapshot.state == "running":
            self.stm.send_resume()

    def on_defect_clicked(self) -> None:
        """'불량 등록' 버튼 클릭 시 작업을 종료하고 STM32로 'R' 명령을 전송합니다."""
        self.work_controller.register_defect()
        self.stm.send_defect()

    def on_logout_clicked(self) -> None:
        """로그아웃 버튼 클릭 시 STM32에 프로그램 종료('E') 명령을 전송하고 로그아웃합니다."""
        self.stm.send_exit()
        self.logout_requested.emit()

    # ── AI 판정 ──────────────────────────────────────────────────────────────

    def request_ai_judgement(self) -> None:
        """최신 Frame과 현재 STEP을 AI Thread에 전달하고 UI는 즉시 반환합니다."""
        if self._ai_busy:
            self.add_log("warning", "이미 AI 판정이 진행 중입니다.")
            return
        if self.work_controller.snapshot.state != "running":
            self.add_log("warning", "작업을 시작한 뒤 AI 판정을 실행하세요.")
            return
        frame = self._latest_frame
        if frame is None:
            self.add_log("warning", "판정할 Camera Frame이 없습니다.")
            return

        current_step = self.work_controller.snapshot.current_step
        product_name = self.work_controller.snapshot.product_name
        product_id = self.work_controller.snapshot.product_id
        self._ai_busy = True
        self.ai_button.setEnabled(False)
        self.ai_button.setText("판정 중...")
        self.ai_thread.submit_frame(
            frame,
            step_no=current_step,
            product_name=product_name,
            product_id=product_id,
        )

    def handle_ai_result(self, result: JudgeResult) -> None:
        """AI Thread 판정 결과를 Controller에 반영하고 STM32로 P/F/C를 전송하며 결과 창을 띄웁니다."""
        self._ai_busy = False
        self.ai_button.setText("AI 판정 실행")
        self.ai_button.setEnabled(self.work_controller.snapshot.state == "running")
        self._update_result_display(result.result.lower(), result.confidence)

        # 현재 STEP이 제품의 마지막 STEP인지 확인
        current_step = self.work_controller.snapshot.current_step
        total_steps = self.work_controller.snapshot.total_steps
        product_name = self.work_controller.snapshot.product_name
        is_final_step = (current_step >= total_steps)

        self.work_controller.apply_judgement(result.result, result.detail)

        # AI 판정 결과에 따른 STM32 명령 전송:
        # - PASS이고 마지막 단계: 'C' 전송 (작업 완료 팡파레 + STEP 0 초기화)
        # - PASS이고 중간 단계: 'P' 전송 (PASS 부저 + 다음 STEP 진입)
        # - FAIL: 'F' 전송 (불량 알람)
        if result.result.upper() == "PASS":
            if is_final_step:
                self.stm.send_complete()
            else:
                self.stm.send_pass()
        else:
            self.stm.send_fail()

        # AI 판정 결과 팝업 창 표시 (좌측: 박스 친 사진, 우측 상단: 결과, 우측 하단: 판정 이유)
        try:
            dialog = AiResultDialog(
                result=result,
                step_no=current_step,
                product_name=product_name,
                parent=self,
            )
            dialog.exec_()
        except Exception as error:
            self.add_log("error", f"판정 결과 팝업 표시 실패: {error}")

    # ── UART / TCP 메시지 처리 ───────────────────────────────────────────────

    def handle_uart_message(self, raw_message: str) -> None:
        """STM32 UART 명령을 파싱하여 작업 상태에 반영하고 시스템 기록에 상세히 남깁니다."""
        message = parse_message(raw_message)
        cmd = message.command

        # STM32 → Qt 수신 명령 디스패치 테이블
        handler = self._uart_handlers.get(cmd)
        if handler:
            handler(message)
        elif cmd.isdigit() or cmd in ("INIT!!!", "BUZZER TEST!!"):
            # STM32 디버그 출력 (숫자 카운터, 테스트 메시지) 무시
            return
        else:
            self.add_log("warning", f"[UART 수신] {message.raw} (미등록 명령)")

    def _on_uart_check(self, message) -> None:
        self.add_log("info", f"[UART 수신] {message.raw} → AI 판정 실행 (STM32 버튼 0)")
        self.request_ai_judgement()

    def _on_uart_pause(self, message) -> None:
        self.add_log("warning", f"[UART 수신] {message.raw} → 공정 일시정지 (STM32 버튼 1)")
        self.work_controller.pause()

    def _on_uart_resume(self, message) -> None:
        self.add_log("info", f"[UART 수신] {message.raw} → 공정 작업 재개 (STM32 버튼 1)")
        self.work_controller.resume()

    def _on_uart_reset(self, message) -> None:
        if self.work_controller.snapshot.state != "running":
            self.add_log("warning", f"[UART 수신] {message.raw} → 무시됨 (일시정지 중이거나 공정 진행 중이 아님)")
            return
        self.add_log("error", f"[UART 수신] {message.raw} → 공정 초기화 / 수동 불량 등록 (STM32 버튼 2)")
        self.work_controller.register_defect()

    def _on_uart_start(self, message) -> None:
        self.add_log("info", f"[UART 수신] {message.raw} → 공정 시작")
        self.on_start_work_clicked()

    def _on_uart_pass(self, message) -> None:
        self.add_log("success", f"[UART 수신] {message.raw} → 판정: PASS")
        self.work_controller.apply_judgement("PASS", "UART 판정: PASS")

    def _on_uart_fail(self, message) -> None:
        self.add_log("error", f"[UART 수신] {message.raw} → 판정: FAIL")
        self.work_controller.apply_judgement("FAIL", "UART 판정: FAIL")

    def handle_tcp_message(self, raw_message: str, address: str) -> None:
        """Monitoring PC 호출 메시지를 UI Main Thread에서 처리합니다."""
        message = parse_message(raw_message)
        self.add_log("info", f"TCP 수신({address}): {message.raw}")

        if message.command == "MESSAGE" and len(message.arguments) >= 2:
            target_id, encoded = message.arguments[0], message.arguments[1]
            if target_id != self.session.employee_id:
                self.add_log("warning", f"다른 직원({target_id}) 대상 메시지를 무시했습니다.")
                return
            text = decode_message_text(encoded)
            if not text:
                self.add_log("warning", "내용을 해석할 수 없는 관리자 메시지입니다.")
                return
            self._show_admin_message_popup(text)

        elif message.command == "CALL" and message.arguments:
            target_id = message.arguments[0]
            current_id = self.work_controller.snapshot.employee_id
            target_text = "현재 작업자" if target_id == current_id else f"직원 {target_id}"
            self.call_message_label.setText(f"관리자 호출이 도착했습니다 · {target_text}")
            self.call_banner.setVisible(True)

        else:
            self.add_log("warning", f"처리하지 않은 TCP 메시지: {message.raw}")

    def _show_admin_message_popup(self, message_text: str) -> None:
        """작업 화면을 막지 않는 별도 창으로 관리자 메시지를 표시합니다."""
        if self.message_popup is not None:
            self.message_popup.close()
        popup = QMessageBox(self)
        popup.setWindowTitle("관리자 메시지")
        popup.setIcon(QMessageBox.Information)
        popup.setText("관리자가 메시지를 보냈습니다.")
        popup.setInformativeText(message_text)
        popup.setStandardButtons(QMessageBox.Ok)
        popup.button(QMessageBox.Ok).setText("확인")
        popup.setModal(False)
        popup.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        popup.finished.connect(lambda _: setattr(self, "message_popup", None))
        self.message_popup = popup
        popup.show()
        popup.raise_()
        popup.activateWindow()

    # ── 장치 상태 ────────────────────────────────────────────────────────────

    def update_device_status(self, label: QLabel, text: str, connected: bool) -> None:
        """장치 연결상태를 초록/빨강 원형 표시로 갱신합니다."""
        label.setText(f"●  {text}")
        label.setStyleSheet(f"color:{'#2F7D4A' if connected else '#B45656'};")
        self.add_log("success" if connected else "error", text)
        if label is self.camera_status and not connected:
            self._latest_frame = None
            self.camera_view.clear()
            self.camera_view.setText(f"카메라 연결 끊김 ({text})\n장치 확인 후 '장치 새로고침'을 누르세요.")

    def refresh_device_connections(self) -> None:
        """'장치 새로고침' 버튼: 끊긴 장치를 재연결합니다."""
        self.device_refresh_button.setEnabled(False)
        self.add_log("info", "장치 연결 상태 확인 및 재연결을 시도합니다.")

        def _check_or_restart(thread, status_label: QLabel, ok_text: str, reconnect_text: str):
            if not thread.isRunning() or (hasattr(thread, "is_connected") and not thread.is_connected()) \
                    or (hasattr(thread, "is_ready") and not thread.is_ready()) \
                    or (hasattr(thread, "is_listening") and not thread.is_listening()):
                status_label.setText(f"●  {reconnect_text}")
                status_label.setStyleSheet("color:#7B8794;")
                thread.restart()
            else:
                self.update_device_status(status_label, ok_text, True)

        backend_name = "테스트" if self.camera_thread.backend == "mock" else self.camera_thread.backend.upper()
        _check_or_restart(self.camera_thread, self.camera_status,
                          f"{backend_name} 카메라 연결", "재연결 중...")
        mode_text = "UART 테스트 모드" if (config.TEST_MODE or not config.UART_ENABLED) \
            else f"UART 연결: {self.uart_thread.port}"
        _check_or_restart(self.uart_thread, self.uart_status, mode_text, "재연결 중...")
        _check_or_restart(self.ai_thread, self.ai_status, "AI 판정 준비", "재시작 중...")
        _check_or_restart(
            self.tcp_thread, self.tcp_status,
            f"TCP 대기: {self.tcp_thread.host}:{self.tcp_thread.port}", "재시작 중...",
        )
        QTimer.singleShot(1000, lambda: self.device_refresh_button.setEnabled(True))

    # ── 서버 연결 감시 ───────────────────────────────────────────────────────

    def _on_monitoring_event_status(self, message: str, ok: bool) -> None:
        """작업상태 전송 실패 시 서버 연결 끊김으로 처리합니다."""
        if not ok:
            self.handle_server_disconnected(message)

    def handle_server_disconnected(self, reason: str = "") -> None:
        """서버 연결 끊김 시 알림창을 표시하고 프로그램을 즉시 종료합니다."""
        if self._is_terminating:
            return
        self._is_terminating = True
        self.server_monitor.set_terminating()
        self.add_log("error", f"서버 연결 끊김: {reason}. 프로그램을 종료합니다.")
        info_text = (
            "관제 PC(모니터링 서버)와의 연결이 끊어져 프로그램을 종료합니다.\n"
            "서버 상태를 확인한 후 프로그램을 다시 실행해 주세요."
        )
        if reason:
            info_text += f"\n\n[상세 정보] {reason}"
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("서버 연결 끊김")
        msg_box.setText("관제 서버와의 연결이 끊어졌습니다.")
        msg_box.setInformativeText(info_text)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.button(QMessageBox.Ok).setText("확인")
        msg_box.exec_()
        self.close()
        QApplication.instance().quit()

    # ── 로그 / 시계 / 종료 ──────────────────────────────────────────────────

    def add_log(self, level: str, message: str) -> None:
        """시간과 Level이 포함된 시스템 기록을 추가합니다."""
        item = QListWidgetItem(f"{datetime.now().strftime('%H:%M:%S')}  {message}")
        item.setForeground(QColor(_LOG_COLORS.get(level, _LOG_DEFAULT_COLOR)))
        self.log_list.addItem(item)
        if self.log_list.count() > 200:
            self.log_list.takeItem(0)
        self.log_list.scrollToBottom()

    def _update_clock(self) -> None:
        self.clock_label.setText(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))

    def closeEvent(self, event) -> None:
        """창 종료 시 STM32에 프로그램 종료 명령 전송 및 모든 Device Thread를 안전하게 정리합니다."""
        self.stm.send_exit()
        self.clock_timer.stop()
        self.server_monitor.stop()
        if self.product_fetch_thread is not None and self.product_fetch_thread.isRunning():
            self.product_fetch_thread.wait(1000)
        if self._guide_fetch_thread is not None and self._guide_fetch_thread.isRunning():
            self._guide_fetch_thread.wait(3500)
        self.monitoring_event_thread.logout_and_stop()
        for thread in (self.camera_thread, self.ai_thread, self.uart_thread, self.tcp_thread):
            thread.stop()
        event.accept()
