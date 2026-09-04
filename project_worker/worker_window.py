"""Jetson 작업자용 메인 PyQt 화면입니다."""

from datetime import datetime
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

import config
from auth_manager import (
    ProductFetchThread, ProductInfo, ServerCheckThread, WorkerSession,
)
from ai_judge import AiInferenceThread, JudgeResult
from camera_manager import CameraThread
from protocol import decode_message_text, parse_message
from tcp_server import TcpServerThread
from uart_manager import UartReceiverThread
from work_state import WorkStateController

try:
    import cv2
except ImportError:
    cv2 = None


class WorkerWindow(QMainWindow):
    """Camera 영상과 공정 제어 상태를 표시하는 작업자 화면입니다."""

    logout_requested = pyqtSignal()

    def __init__(self, session: WorkerSession):
        super().__init__()
        self.session = session
        self.setWindowTitle("공정 모니터링 · 작업자 프로그램")
        self.setMinimumSize(1120, 720)
        self.resize(1360, 1000)
        self._latest_frame = None
        self._ai_busy = False
        self._services_started = False
        self.products = []
        self._current_product = None
        self.product_fetch_thread = None
        self.server_check_thread = None
        self._is_terminating = False
        self._saved_work_restored = False
        self.server_monitor_timer = QTimer(self)
        self.server_monitor_timer.timeout.connect(self._auto_check_server)
        self.message_popup = None

        self.work_controller = WorkStateController()
        self.camera_thread = CameraThread()
        self.ai_thread = AiInferenceThread()
        self.uart_thread = UartReceiverThread()
        self.tcp_thread = TcpServerThread()

        self._create_ui()
        self._connect_signals()
        self._load_test_defaults()
        QTimer.singleShot(0, self.start_services)

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
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("mutedText")
            subtitle_label.setStyleSheet("font-size:11px;")
            layout.addWidget(subtitle_label)
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

    def _create_ui(self) -> None:
        """작업 설정, 영상, STEP 제어, 장치 상태 화면을 구성합니다."""
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(68)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(26, 0, 26, 0)
        logo = QLabel("FM")
        logo.setFixedSize(38, 38)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            "color:#FFFFFF; background:#315E91; border-radius:8px; font-weight:900;"
        )
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
        logout_button.clicked.connect(self.logout_requested.emit)
        top_layout.addWidget(logo)
        top_layout.addWidget(app_name)
        top_layout.addStretch()
        top_layout.addWidget(user_label)
        top_layout.addSpacing(12)
        top_layout.addWidget(logout_button)
        top_layout.addSpacing(12)
        top_layout.addWidget(self.clock_label)

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

        camera_card, camera_layout = self._make_card(
            "카메라", "USB Camera와 Jetson CSI Camera Backend를 지원합니다."
        )
        self.camera_view = QLabel("카메라 연결 대기 중")
        self.camera_view.setAlignment(Qt.AlignCenter)
        self.camera_view.setMinimumSize(620, 320)
        self.camera_view.setStyleSheet(
            "color:#C7D2DC; background:#263746; border:1px solid #BFC9D3; "
            "border-radius:7px;"
        )
        camera_layout.addWidget(self.camera_view, 1)

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

        control_grid = QGridLayout()
        self.start_button = QPushButton("작업 시작")
        self.start_button.setObjectName("primaryButton")
        self.pause_button = QPushButton("일시정지")
        self.pause_button.setObjectName("warningButton")
        self.resume_button = QPushButton("작업 재개")
        self.defect_button = QPushButton("불량 등록")
        self.defect_button.setObjectName("dangerButton")
        self.defect_button.setEnabled(False)
        self.start_button.clicked.connect(self.work_controller.start)
        self.pause_button.clicked.connect(self.work_controller.pause)
        self.resume_button.clicked.connect(self.work_controller.resume)
        self.defect_button.clicked.connect(self.work_controller.register_defect)
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
        for status_item in (camera_item, ai_item, uart_item, tcp_item):
            status_layout.addWidget(status_item, 1)

        self.device_refresh_button = QPushButton("장치 새로고침")
        self.device_refresh_button.setCursor(Qt.PointingHandCursor)
        self.device_refresh_button.setToolTip("장치 연결 상태를 확인하고 끊어진 장치의 재연결을 시도합니다.")
        status_layout.addWidget(self.device_refresh_button)

        main_row = QHBoxLayout()
        main_row.setSpacing(14)
        main_row.addWidget(camera_card, 2)
        progress_card.setMinimumWidth(390)
        main_row.addWidget(progress_card, 1)

        log_card, log_layout = self._make_card("시스템 기록")
        self.log_list = QListWidget()
        self.log_list.setAlternatingRowColors(True)
        self.log_list.setMaximumHeight(90)
        log_layout.addWidget(self.log_list)

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

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)
        self._update_clock()

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

    def _connect_signals(self) -> None:
        """Thread와 상태 Controller 신호를 UI Slot에 연결합니다."""
        self.work_controller.state_changed.connect(self.update_work_state)
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

    def _load_test_defaults(self) -> None:
        """초기 실행 시 모니터링 PC products 테이블에서 제품 목록을 로드합니다."""
        self.fetch_products()

    def fetch_products(self) -> None:
        """모니터링 PC의 products 테이블로부터 제품 목록을 비동기 조회합니다."""
        if self.product_fetch_thread is not None and self.product_fetch_thread.isRunning():
            return
        self.product_fetch_thread = ProductFetchThread(
            token=self.session.token,
            parent=self,
        )
        self.product_fetch_thread.products_fetched.connect(self._on_products_fetched)
        self.product_fetch_thread.finished.connect(self._clear_product_fetch_thread)
        self.product_fetch_thread.start()

    def _clear_product_fetch_thread(self) -> None:
        """조회 완료된 스레드 참조를 해제합니다."""
        self.product_fetch_thread = None

    def _on_products_fetched(self, products: list, success: bool, message: str) -> None:
        """가져온 제품 목록을 드롭다운에 채우고, 이전 작업이 남아있으면 복원합니다."""
        self.products = products
        self.product_name_combo.blockSignals(True)
        self.product_name_combo.clear()
        for prod in self.products:
            self.product_name_combo.addItem(f"{prod.product_name} ({prod.product_id})", prod)
        self.product_name_combo.blockSignals(False)

        # 로그인 후 최초 1회: 서버에 이전 작업이 남아있는지 확인하여 복원
        if not self._saved_work_restored:
            restored = self._try_restore_previous_work()
            if restored:
                self._saved_work_restored = True
                self.add_log("info" if success else "warning", message)
                return

        if self.products:
            self._on_product_changed(self.product_name_combo.currentIndex())
        else:
            self._current_product = None
            self.product_id_display.clear()
            self.total_steps_display.clear()
        self.add_log("info" if success else "warning", message)
        if not success and ("연결" in message or "네트워크" in message or "Connection" in message):
            self.handle_server_disconnected("제품 목록 조회 중 서버 연결이 끊겼습니다.")

    def _try_restore_previous_work(self) -> bool:
        """서버 로그인 시 수신된 이전 작업 내용이 남아있는 경우 복원하여 이어서 진행할 수 있게 합니다."""
        saved_state = getattr(self.session, "saved_state", None)
        if not saved_state:
            return False

        product_id = saved_state.get("product_id")
        if not product_id:
            return False

        # 1. 제품 목록에서 일치하는 제품 찾기
        target_product = None
        target_index = -1
        for idx, prod in enumerate(self.products):
            if prod.product_id == product_id:
                target_product = prod
                target_index = idx
                break

        if target_product is None:
            total_steps = max(1, int(saved_state.get("total_steps") or 1))
            product_name = str(saved_state.get("product_name") or product_id)
            target_product = ProductInfo(
                product_id=product_id,
                product_name=product_name,
                total_steps=total_steps,
            )
            self.products.append(target_product)
            self.product_name_combo.addItem(
                f"{target_product.product_name} ({target_product.product_id})",
                target_product,
            )
            target_index = self.product_name_combo.count() - 1

        # 2. UI 제품 선택 동기화 (configure 호출 방지를 위해 blockSignals)
        self.product_name_combo.blockSignals(True)
        self.product_name_combo.setCurrentIndex(target_index)
        self.product_name_combo.blockSignals(False)

        self._current_product = target_product
        self.product_id_display.setText(target_product.product_id)
        total_steps = max(1, int(saved_state.get("total_steps") or target_product.total_steps))
        self.total_steps_display.setText(f"{total_steps} 단계")

        # 3. Controller에 이전 작업 상태 복원 (WorkSnapshot 복원 및 UI/이벤트 브로드캐스트)
        self.work_controller.restore_state(
            employee_id=self.session.employee_id,
            employee_name=self.session.name,
            saved_state=saved_state,
        )

        current_step = saved_state.get("current_step", 1)
        state_name = saved_state.get("state", "running")
        state_str = "작업 진행 중" if state_name == "running" else "일시정지"

        self.add_log(
            "success",
            f"서버 이전 작업 복원 완료: {target_product.product_name} (STEP {current_step}/{total_steps}) - 작업을 계속 진행합니다."
        )

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
        """드롭다운에서 제품 선택 시 제품번호와 전체 STEP을 고정 표시하고 작업 정보를 갱신합니다."""
        if index < 0 or index >= len(self.products):
            product = self.product_name_combo.currentData()
            if product is None:
                return
        else:
            product = self.products[index]

        self._current_product = product
        self.product_id_display.setText(product.product_id)
        self.total_steps_display.setText(f"{product.total_steps} 단계")
        self.apply_work_setup(silent=True)

    def start_services(self) -> None:
        """Camera, AI, UART, TCP Thread를 한 번만 시작합니다."""
        if self._services_started:
            return
        self._services_started = True
        for thread in (
            self.camera_thread, self.ai_thread, self.uart_thread, self.tcp_thread
        ):
            thread.start()
        self.add_log("info", "작업자 프로그램 서비스를 시작했습니다.")
        self.server_monitor_timer.start(2000)

    def apply_work_setup(self, silent: bool = False) -> None:
        """선택된 제품 정보를 Controller에 적용합니다."""
        if self._current_product is None:
            if not silent:
                QMessageBox.information(self, "작업 정보", "선택된 제품이 없습니다.")
            return
        self.work_controller.configure(
            self.session.employee_id, self.session.name,
            self._current_product.product_id, self._current_product.product_name,
            self._current_product.total_steps,
        )

    def update_work_state(self, state: dict) -> None:
        """Controller 상태를 STEP, Progress, Button에 반영합니다."""
        state_name = state["state"]
        state_text = {
            "idle": "작업 대기", "running": "작업 진행 중",
            "paused": "일시정지", "complete": "작업 완료",
        }.get(state_name, state_name)
        state_color = {
            "idle": ("#5F6D7A", "#F1F4F6"),
            "running": ("#2F7651", "#EAF5EE"),
            "paused": ("#8A641F", "#FFF6DF"),
            "complete": ("#315E91", "#EAF1F8"),
        }.get(state_name, ("#5F6D7A", "#F1F4F6"))
        self.state_badge.setText(f"●  {state_text}")
        self.state_badge.setStyleSheet(
            f"color:{state_color[0]}; background:{state_color[1]}; "
            "border-radius:6px; font-weight:700;"
        )
        self.current_step_label.setText(
            f"STEP {state['current_step']} / {state['total_steps']}"
        )
        self.work_progress.setRange(0, state["total_steps"])
        if state_name == "complete":
            completed_steps = state["total_steps"]
        elif state["current_step"] == 0:
            completed_steps = 0
        else:
            completed_steps = state["current_step"] - 1
        self.work_progress.setValue(max(0, completed_steps))
        self._update_result_display(state["last_result"])
        is_idle = (state_name in ("idle", "complete"))
        self.product_name_combo.setEnabled(is_idle)
        self.refresh_button.setEnabled(is_idle)
        self.start_button.setEnabled(is_idle and self._current_product is not None)
        self.pause_button.setEnabled(state_name == "running")
        self.resume_button.setEnabled(state_name == "paused")
        self.defect_button.setEnabled(state_name == "running")
        self.ai_button.setEnabled(state_name == "running" and not self._ai_busy)

    def _update_result_display(self, result: str,
                               confidence: Optional[float] = None) -> None:
        """판정 상태를 색상과 텍스트로 표시합니다."""
        if result == "pass":
            text, foreground, background = "PASS", "#2F7651", "#EAF5EE"
        elif result == "fail":
            text, foreground, background = "FAIL", "#AE5050", "#FCEEEE"
        else:
            text, foreground, background = "판정 대기", "#6F7B89", "#F4F6F8"
        if confidence is not None:
            text += f"  ·  {confidence * 100:.1f}%"
        self.result_label.setText(text)
        self.result_label.setStyleSheet(
            f"color:{foreground}; background:{background}; border:1px solid #DDE3EA; "
            "border-radius:7px; font-size:20px; font-weight:700;"
        )

    def update_camera_frame(self, frame) -> None:
        """Camera Thread의 Frame을 화면에 최적화하여 표시하고 최신 Frame을 보관합니다."""
        self._latest_frame = frame
        if frame is None:
            return

        if isinstance(frame, QImage):
            pixmap = QPixmap.fromImage(frame)
            self.camera_view.setPixmap(
                pixmap.scaled(self.camera_view.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
            )
        elif cv2 is not None:
            view_size = self.camera_view.size()
            vw, vh = view_size.width(), view_size.height()
            if vw > 10 and vh > 10:
                fh, fw = frame.shape[:2]
                scale = min(vw / fw, vh / fh)
                nw, nh = max(1, int(fw * scale)), max(1, int(fh * scale))
                # OpenCV의 SIMD 가속 리사이즈가 CPU SmoothTransformation보다 훨씬 빠름
                resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
                rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
                image = QImage(rgb_frame.data, nw, nh, nw * 3, QImage.Format_RGB888)
                self.camera_view.setPixmap(QPixmap.fromImage(image))
            else:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                fh, fw, _ = rgb_frame.shape
                image = QImage(rgb_frame.data, fw, fh, fw * 3, QImage.Format_RGB888)
                self.camera_view.setPixmap(QPixmap.fromImage(image))

    def request_ai_judgement(self) -> None:
        """최신 Frame을 AI Thread에 전달하고 UI는 즉시 반환합니다."""
        if self._latest_frame is None:
            self.add_log("warning", "판정할 Camera Frame이 없습니다.")
            return
        if self.work_controller.snapshot.state != "running":
            self.add_log("warning", "작업을 시작한 뒤 AI 판정을 실행하세요.")
            return
        self._ai_busy = True
        self.ai_button.setEnabled(False)
        self.ai_button.setText("판정 중...")
        self.ai_thread.submit_frame(self._latest_frame)

    def handle_ai_result(self, result: JudgeResult) -> None:
        """AI Thread 판정 결과를 Controller에 반영합니다."""
        self._ai_busy = False
        self.ai_button.setText("AI 판정 실행")
        self.ai_button.setEnabled(self.work_controller.snapshot.state == "running")
        self._update_result_display(result.result.lower(), result.confidence)
        self.work_controller.apply_judgement(result.result, result.detail)

    def handle_uart_message(self, raw_message: str) -> None:
        """STM32 UART 명령을 파싱하여 작업 상태에 반영합니다."""
        message = parse_message(raw_message)
        self.add_log("info", f"UART 수신: {message.raw}")
        if message.command in ("PASS", "FAIL"):
            self.work_controller.apply_judgement(message.command, "UART 판정: " + message.command)
        elif message.command == "PAUSE":
            self.work_controller.pause()
        elif message.command == "RESUME":
            self.work_controller.resume()
        elif message.command == "RESET":
            self.work_controller.reset()
        elif message.command == "START":
            self.work_controller.start()
        else:
            self.add_log("warning", f"처리하지 않은 UART 명령: {message.raw}")

    def handle_tcp_message(self, raw_message: str, address: str) -> None:
        """Monitoring PC 호출 메시지를 UI Main Thread에서 처리합니다."""
        message = parse_message(raw_message)
        self.add_log("info", f"TCP 수신({address}): {message.raw}")
        if message.command == "MESSAGE" and len(message.arguments) >= 2:
            target_id = message.arguments[0]
            if target_id != self.session.employee_id:
                self.add_log("warning", f"다른 직원({target_id}) 대상 메시지를 무시했습니다.")
                return
            message_text = decode_message_text(message.arguments[1])
            if not message_text:
                self.add_log("warning", "내용을 해석할 수 없는 관리자 메시지입니다.")
                return
            self._show_admin_message_popup(message_text)
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
        popup.finished.connect(self._clear_message_popup)
        self.message_popup = popup
        popup.show()
        popup.raise_()
        popup.activateWindow()

    def _clear_message_popup(self, _result: int) -> None:
        """관리자 메시지 팝업 참조를 종료 후 정리합니다."""
        self.message_popup = None

    def update_device_status(self, label: QLabel, text: str, connected: bool) -> None:
        """장치 연결상태를 초록/빨강 원형 표시로 갱신합니다."""
        color = "#2F7D4A" if connected else "#B45656"
        label.setText(f"●  {text}")
        label.setStyleSheet(f"color:{color};")
        self.add_log("success" if connected else "error", text)
        if label == self.camera_status and not connected:
            self._latest_frame = None
            self.camera_view.clear()
            self.camera_view.setText(f"카메라 연결 끊김 ({text})\n장치 확인 후 '장치 새로고침'을 누르세요.")

    def refresh_device_connections(self) -> None:
        """사용자가 '장치 새로고침' 버튼을 눌렀을 때만 장치 상태를 다시 확인하고 재연결을 시도합니다."""
        self.device_refresh_button.setEnabled(False)
        self.add_log("info", "장치 연결 상태 확인 및 재연결을 시도합니다.")

        # 1. Camera 확인 및 재연결
        if not self.camera_thread.is_connected():
            self.camera_status.setText("●  재연결 중...")
            self.camera_status.setStyleSheet("color:#7B8794;")
            self.camera_thread.restart()
        else:
            backend_name = (
                "테스트" if self.camera_thread.backend == "mock"
                else self.camera_thread.backend.upper()
            )
            self.update_device_status(self.camera_status, f"{backend_name} 카메라 연결", True)

        # 2. UART 확인 및 재연결
        if not self.uart_thread.is_connected():
            self.uart_status.setText("●  재연결 중...")
            self.uart_status.setStyleSheet("color:#7B8794;")
            self.uart_thread.restart()
        else:
            mode_text = (
                "UART 테스트 모드" if config.TEST_MODE or not config.UART_ENABLED
                else f"UART 연결: {self.uart_thread.port}"
            )
            self.update_device_status(self.uart_status, mode_text, True)

        # 3. AI 추론 확인 및 재시작
        if not self.ai_thread.is_ready():
            self.ai_status.setText("●  재시작 중...")
            self.ai_status.setStyleSheet("color:#7B8794;")
            self.ai_thread.restart()
        else:
            self.update_device_status(self.ai_status, "AI 판정 준비", True)

        # 4. TCP Server 확인 및 재시작
        if not self.tcp_thread.is_listening():
            self.tcp_status.setText("●  재시작 중...")
            self.tcp_status.setStyleSheet("color:#7B8794;")
            self.tcp_thread.restart()
        else:
            self.update_device_status(
                self.tcp_status,
                f"TCP 대기: {self.tcp_thread.host}:{self.tcp_thread.port}",
                True,
            )

        QTimer.singleShot(1000, lambda: self.device_refresh_button.setEnabled(True))

    def handle_monitoring_event_status(self, message: str, ok: bool) -> None:
        """작업상태 전송 중 서버 통신 실패 시 알림창을 띄우고 프로그램을 종료합니다."""
        if not ok:
            self.handle_server_disconnected(message)

    def _auto_check_server(self) -> None:
        """주기적으로 백그라운드에서 관제 서버 연결 상태를 점검합니다."""
        if config.TEST_MODE or getattr(self, "_is_terminating", False):
            return
        if self.server_check_thread is not None and self.server_check_thread.isRunning():
            return

        self.server_check_thread = ServerCheckThread(timeout=1.0, parent=self)
        self.server_check_thread.check_finished.connect(self._on_auto_server_check_finished)
        self.server_check_thread.finished.connect(self._clear_server_check_thread)
        self.server_check_thread.start()

    def _clear_server_check_thread(self) -> None:
        """점검 완료된 스레드 참조를 해제합니다."""
        self.server_check_thread = None

    def _on_auto_server_check_finished(self, ok: bool, message: str) -> None:
        """서버 연결 끊김 감지 시 알림창을 띄우고 프로그램을 종료합니다."""
        if getattr(self, "_is_terminating", False):
            return
        if not ok:
            self.handle_server_disconnected(message)

    def handle_server_disconnected(self, reason: str = "") -> None:
        """서버 연결 끊김 시 알림창을 표시하고 프로그램을 즉시 종료합니다."""
        if getattr(self, "_is_terminating", False):
            return
        self._is_terminating = True
        self.server_monitor_timer.stop()
        self.add_log("error", f"서버 연결 끊김: {reason}. 프로그램을 종료합니다.")

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("서버 연결 끊김")
        msg_box.setText("관제 서버와의 연결이 끊어졌습니다.")
        info_text = (
            "관제 PC(모니터링 서버)와의 연결이 끊어져 프로그램을 종료합니다.\n"
            "서버 상태를 확인한 후 프로그램을 다시 실행해 주세요."
        )
        if reason:
            info_text += f"\n\n[상세 정보] {reason}"
        msg_box.setInformativeText(info_text)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.button(QMessageBox.Ok).setText("확인")
        msg_box.exec_()

        self.close()
        QApplication.instance().quit()

    def add_log(self, level: str, message: str) -> None:
        """시간과 Level이 포함된 시스템 기록을 추가합니다."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        item = QListWidgetItem(f"{timestamp}  {message}")
        item.setForeground(QColor({
            "success": "#2F7651", "warning": "#8A641F",
            "error": "#AE5050", "info": "#526170",
        }.get(level, "#526170")))
        self.log_list.addItem(item)
        self.log_list.scrollToBottom()

    def _update_clock(self) -> None:
        self.clock_label.setText(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))

    def closeEvent(self, event) -> None:
        """창 종료 시 모든 Device Thread를 안전하게 정리합니다."""
        self.clock_timer.stop()
        self.server_monitor_timer.stop()
        if self.server_check_thread is not None and self.server_check_thread.isRunning():
            self.server_check_thread.wait(1000)
        if self.product_fetch_thread is not None and self.product_fetch_thread.isRunning():
            self.product_fetch_thread.wait(1000)
        for thread in (
            self.camera_thread, self.ai_thread, self.uart_thread, self.tcp_thread
        ):
            thread.stop()
        event.accept()
