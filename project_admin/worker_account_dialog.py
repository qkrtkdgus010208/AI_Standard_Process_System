"""작업자 계정 등록과 말소 입력을 받는 관리자 Dialog입니다."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout,
)


class WorkerRegistrationDialog(QDialog):
    """새 작업자 계정에 필요한 값만 입력받습니다."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("작업자 계정 등록")
        self.setFixedSize(440, 410)
        self._create_ui()

    def _create_ui(self) -> None:
        title = QLabel("새 작업자 계정")
        title.setObjectName("pageTitle")
        subtitle = QLabel("관리자 계정은 생성할 수 없으며 권한은 작업자로 고정됩니다.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        self.employee_id_input = QLineEdit()
        self.employee_id_input.setPlaceholderText("예: 1002")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("작업자 이름")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("6자 이상 비밀번호")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_confirm_input = QLineEdit()
        self.password_confirm_input.setPlaceholderText("비밀번호 확인")
        self.password_confirm_input.setEchoMode(QLineEdit.Password)
        self.password_confirm_input.returnPressed.connect(self._validate_and_accept)

        form = QFormLayout()
        form.setSpacing(12)
        form.addRow("직원번호", self.employee_id_input)
        form.addRow("이름", self.name_input)
        form.addRow("비밀번호", self.password_input)
        form.addRow("비밀번호 확인", self.password_confirm_input)

        cancel_button = QPushButton("취소")
        cancel_button.clicked.connect(self.reject)
        register_button = QPushButton("작업자 계정 등록")
        register_button.setObjectName("primaryButton")
        register_button.clicked.connect(self._validate_and_accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel_button)
        buttons.addWidget(register_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addLayout(form)
        layout.addStretch()
        layout.addLayout(buttons)

    def _validate_and_accept(self) -> None:
        employee_id = self.employee_id_input.text().strip()
        name = self.name_input.text().strip()
        password = self.password_input.text()
        if not employee_id or not name or not password:
            QMessageBox.information(
                self, "입력 확인", "직원번호, 이름, 비밀번호를 모두 입력하세요."
            )
            return
        if len(password) < 6:
            QMessageBox.information(self, "입력 확인", "비밀번호는 6자 이상으로 설정하세요.")
            self.password_input.setFocus()
            return
        if password != self.password_confirm_input.text():
            QMessageBox.information(self, "입력 확인", "비밀번호 확인이 일치하지 않습니다.")
            self.password_confirm_input.setFocus()
            return
        self.accept()

    def worker_data(self) -> dict:
        return {
            "employee_id": self.employee_id_input.text().strip(),
            "name": self.name_input.text().strip(),
            "password": self.password_input.text(),
        }


class WorkerRevocationDialog(QDialog):
    """말소할 작업자 직원번호를 입력받습니다."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("작업자 계정 말소")
        self.setFixedSize(420, 245)
        self._create_ui()

    def _create_ui(self) -> None:
        title = QLabel("작업자 계정 말소")
        title.setObjectName("pageTitle")
        subtitle = QLabel("말소할 작업자의 직원번호를 입력하세요.")
        subtitle.setObjectName("subtitle")
        self.employee_id_input = QLineEdit()
        self.employee_id_input.setPlaceholderText("직원번호")
        self.employee_id_input.returnPressed.connect(self._validate_and_accept)

        cancel_button = QPushButton("취소")
        cancel_button.clicked.connect(self.reject)
        revoke_button = QPushButton("말소")
        revoke_button.setObjectName("dangerButton")
        revoke_button.clicked.connect(self._validate_and_accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel_button)
        buttons.addWidget(revoke_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.employee_id_input)
        layout.addStretch()
        layout.addLayout(buttons)

    def _validate_and_accept(self) -> None:
        if not self.employee_id_input.text().strip():
            QMessageBox.information(self, "입력 확인", "말소할 직원번호를 입력하세요.")
            self.employee_id_input.setFocus()
            return
        self.accept()

    def employee_id(self) -> str:
        return self.employee_id_input.text().strip()


class WorkerRevocationConfirmDialog(QDialog):
    """말소 대상의 신원과 작업 정보를 카드 형태로 최종 확인합니다."""

    def __init__(self, summary: dict, parent=None):
        super().__init__(parent)
        self.summary = summary
        self.setWindowTitle("계정 말소 최종 확인")
        self.setFixedSize(600, 650)
        self._create_ui()

    @staticmethod
    def _detail_tile(caption: str, value: str, value_color: str = "#263442") -> QFrame:
        tile = QFrame()
        tile.setObjectName("card")
        tile.setMinimumHeight(72)
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(15, 11, 15, 11)
        layout.setSpacing(4)
        caption_label = QLabel(caption)
        caption_label.setObjectName("metricLabel")
        value_label = QLabel(value)
        value_label.setWordWrap(True)
        value_label.setStyleSheet(
            f"color:{value_color};font-size:14px;font-weight:700;border:none;"
        )
        layout.addWidget(caption_label)
        layout.addWidget(value_label)
        return tile

    def _create_ui(self) -> None:
        eyebrow = QLabel("ACCOUNT MANAGEMENT  ·  FINAL CHECK")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("계정 말소 전 확인")
        title.setObjectName("pageTitle")
        subtitle = QLabel("대상 작업자의 신원과 현재 작업 정보를 확인해 주세요.")
        subtitle.setObjectName("subtitle")

        profile = QFrame()
        profile.setObjectName("card")
        profile_layout = QHBoxLayout(profile)
        profile_layout.setContentsMargins(18, 16, 18, 16)
        profile_layout.setSpacing(14)
        avatar = QLabel("ID")
        avatar.setFixedSize(54, 54)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            "color:#FFFFFF;background:#315E91;border-radius:12px;"
            "font-size:15px;font-weight:900;border:none;"
        )
        identity = QVBoxLayout()
        identity.setSpacing(3)
        name_label = QLabel(str(self.summary["name"]))
        name_label.setStyleSheet("font-size:18px;font-weight:800;color:#202936;border:none;")
        id_label = QLabel(f"직원번호  {self.summary['employee_id']}")
        id_label.setObjectName("subtitle")
        identity.addWidget(name_label)
        identity.addWidget(id_label)
        role_badge = QLabel("생산 작업자")
        role_badge.setAlignment(Qt.AlignCenter)
        role_badge.setFixedSize(88, 30)
        role_badge.setStyleSheet(
            "color:#315E91;background:#EAF1F8;border:1px solid #C9D9E9;"
            "border-radius:14px;font-size:11px;font-weight:700;"
        )
        profile_layout.addWidget(avatar)
        profile_layout.addLayout(identity, 1)
        profile_layout.addWidget(role_badge)

        status_color = "#2F7D4A" if self.summary["attendance"] == "출근 중" else "#6F7B89"
        details = QGridLayout()
        details.setHorizontalSpacing(10)
        details.setVerticalSpacing(10)
        tiles = (
            self._detail_tile("출근 상태", self.summary["attendance"], status_color),
            self._detail_tile("최근 로그인", self.summary["latest_login"]),
            self._detail_tile("진행 중 제품", self.summary["active_product"], "#315E91"),
            self._detail_tile("현재 공정", self.summary["current_step"], "#315E91"),
            self._detail_tile("누적 제품 작업", f"{self.summary['product_run_count']}건"),
            self._detail_tile("불량 이력", f"{self.summary['defect_count']}건", "#B45656"),
        )
        for index, tile in enumerate(tiles):
            details.addWidget(tile, index // 2, index % 2)

        warning = QFrame()
        warning.setStyleSheet(
            "QFrame { background:#FFF5F5;border:1px solid #E7CACA;border-radius:9px; }"
            "QLabel { border:none;background:transparent; }"
        )
        warning_layout = QHBoxLayout(warning)
        warning_layout.setContentsMargins(15, 12, 15, 12)
        warning_layout.setSpacing(11)
        warning_icon = QLabel("!")
        warning_icon.setFixedSize(30, 30)
        warning_icon.setAlignment(Qt.AlignCenter)
        warning_icon.setStyleSheet(
            "color:#FFFFFF;background:#B64A4A;border-radius:15px;font-weight:900;"
        )
        warning_text = QVBoxLayout()
        warning_text.setSpacing(2)
        warning_title = QLabel("말소 후에는 작업자 프로그램에 로그인할 수 없습니다.")
        warning_title.setStyleSheet("color:#963D3D;font-weight:700;")
        warning_description = QLabel("기존 출퇴근·작업·불량 이력은 삭제되지 않고 보존됩니다.")
        warning_description.setStyleSheet("color:#8A5C5C;font-size:11px;")
        warning_text.addWidget(warning_title)
        warning_text.addWidget(warning_description)
        warning_layout.addWidget(warning_icon)
        warning_layout.addLayout(warning_text, 1)

        cancel_button = QPushButton("취소")
        cancel_button.setMinimumWidth(96)
        cancel_button.clicked.connect(self.reject)
        revoke_button = QPushButton("계정 말소")
        revoke_button.setMinimumWidth(120)
        revoke_button.setStyleSheet(
            "QPushButton { color:#FFFFFF;background:#B64A4A;border:1px solid #B64A4A;"
            "border-radius:6px;font-weight:700; }"
            "QPushButton:hover { background:#9F3D3D;border-color:#9F3D3D; }"
            "QPushButton:pressed { background:#873333;border-color:#873333; }"
        )
        revoke_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel_button)
        buttons.addWidget(revoke_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(profile)
        layout.addLayout(details)
        layout.addWidget(warning)
        layout.addStretch()
        layout.addLayout(buttons)
