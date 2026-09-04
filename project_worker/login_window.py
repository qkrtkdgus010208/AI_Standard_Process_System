"""작업자 전용 로그인 화면입니다."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QVBoxLayout, QWidget,
)

import config
from auth_manager import AuthRequestThread, AuthResult


class WorkerLoginWindow(QMainWindow):
    """일반 작업자 계정만 인증하고 Session을 발급받는 화면입니다."""

    login_succeeded = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.auth_thread = None
        self.setWindowTitle("공정 모니터링 · 작업자 로그인")
        self.setFixedSize(820, 520)
        self._create_ui()

    def _create_ui(self) -> None:
        """안내 패널과 작업자 로그인 Form을 구성합니다."""
        info_panel = QFrame()
        info_panel.setObjectName("brandPanel")
        info_panel.setStyleSheet(
            "QFrame#brandPanel{background:#E9EFF6;border:1px solid #D4DEE9;border-radius:12px;}"
        )
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(36, 36, 36, 36)
        logo = QLabel("FM")
        logo.setFixedSize(46, 46)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(
            "color:#FFFFFF;background:#315E91;border-radius:10px;font-weight:900;"
        )
        title = QLabel("공정 모니터링\n작업자 프로그램")
        title.setStyleSheet("color:#1F2C39;font-size:27px;font-weight:700;")
        description = QLabel(
            "본인 계정으로 로그인한 후 배정된 작업을 진행하세요.\n"
            "작업 기록은 로그인한 직원번호로만 전송됩니다."
        )
        description.setObjectName("subtitle")
        security = QLabel("●  개인 작업 세션 보호")
        security.setStyleSheet("color:#397653;font-size:11px;font-weight:700;")
        info_layout.addWidget(logo)
        info_layout.addSpacing(28)
        info_layout.addWidget(title)
        info_layout.addWidget(description)
        info_layout.addStretch()
        info_layout.addWidget(security)

        login_card = QFrame()
        login_card.setObjectName("card")
        login_layout = QVBoxLayout(login_card)
        login_layout.setContentsMargins(34, 34, 34, 34)
        login_layout.setSpacing(9)
        card_title = QLabel("작업자 로그인")
        card_title.setObjectName("pageTitle")
        card_subtitle = QLabel("등록된 작업자 계정으로 로그인하세요.")
        card_subtitle.setObjectName("subtitle")
        id_label = QLabel("직원번호")
        id_label.setObjectName("smallLabel")
        self.employee_id_input = QLineEdit()
        self.employee_id_input.setPlaceholderText("직원번호 입력")
        password_label = QLabel("비밀번호")
        password_label.setObjectName("smallLabel")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("비밀번호 입력")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.try_login)
        self.error_label = QLabel("")
        self.error_label.setMinimumHeight(38)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color:#B45656;font-size:11px;")
        self.login_button = QPushButton("로그인")
        self.login_button.setObjectName("primaryButton")
        self.login_button.clicked.connect(self.try_login)
        login_layout.addWidget(card_title)
        login_layout.addWidget(card_subtitle)
        login_layout.addSpacing(18)
        login_layout.addWidget(id_label)
        login_layout.addWidget(self.employee_id_input)
        login_layout.addSpacing(5)
        login_layout.addWidget(password_label)
        login_layout.addWidget(self.password_input)
        login_layout.addWidget(self.error_label)
        login_layout.addWidget(self.login_button)
        login_layout.addStretch()
        if config.TEST_MODE:
            test_info = QLabel("TEST 계정  ·  1001 / worker1234")
            test_info.setAlignment(Qt.AlignCenter)
            test_info.setObjectName("mutedText")
            test_info.setStyleSheet("font-size:10px;")
            login_layout.addWidget(test_info)

        layout = QHBoxLayout()
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(22)
        layout.addWidget(info_panel, 1)
        layout.addWidget(login_card, 1)
        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)
        self.employee_id_input.setFocus()

    def try_login(self) -> None:
        """입력값을 별도 Thread에서 인증합니다."""
        employee_id = self.employee_id_input.text().strip()
        password = self.password_input.text()
        if not employee_id or not password:
            self.error_label.setText("직원번호와 비밀번호를 모두 입력하세요.")
            return
        if self.auth_thread is not None and self.auth_thread.isRunning():
            return
        self.login_button.setEnabled(False)
        self.login_button.setText("확인 중...")
        self.error_label.clear()
        self.auth_thread = AuthRequestThread(employee_id, password, self)
        self.auth_thread.completed.connect(self._handle_auth_result)
        self.auth_thread.finished.connect(self._clear_auth_thread)
        self.auth_thread.start()

    def _clear_auth_thread(self) -> None:
        """인증 완료된 스레드 참조를 해제합니다."""
        self.auth_thread = None

    def _handle_auth_result(self, result: AuthResult) -> None:
        """인증 결과에 따라 오류를 표시하거나 Session을 전달합니다."""
        self.login_button.setEnabled(True)
        self.login_button.setText("로그인")
        if not result.success or result.session is None:
            self.error_label.setText(result.message)
            self.password_input.clear()
            self.password_input.setFocus()
            return
        self.password_input.clear()
        self.login_succeeded.emit(result.session)
