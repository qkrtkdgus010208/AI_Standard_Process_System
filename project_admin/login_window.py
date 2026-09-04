"""관리자 로그인 창입니다."""

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from database_manager import DatabaseManager
from theme import add_card_shadow


class ProcessFlowIllustration(QWidget):
    """작업자부터 품질검사까지의 공정 흐름을 아이콘으로 표현합니다."""

    LABELS = ("작업자", "제품", "STEP", "품질검사")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = self.width()
        centers = [width * ratio for ratio in (0.12, 0.37, 0.63, 0.88)]
        center_y = 60.0
        radius = 28.0

        connection_pen = QPen(QColor("#AFC0D1"), 2)
        connection_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(connection_pen)
        for left, right in zip(centers, centers[1:]):
            start_x = left + radius + 7
            end_x = right - radius - 9
            painter.drawLine(QPointF(start_x, center_y), QPointF(end_x, center_y))
            painter.setBrush(QColor("#AFC0D1"))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygonF([
                QPointF(end_x + 7, center_y),
                QPointF(end_x - 1, center_y - 5),
                QPointF(end_x - 1, center_y + 5),
            ]))
            painter.setPen(connection_pen)

        for index, center_x in enumerate(centers):
            node = QRectF(center_x - radius, center_y - radius,
                          radius * 2, radius * 2)
            painter.setPen(QPen(QColor("#C8D5E2"), 1.3))
            painter.setBrush(QColor(255, 255, 255, 232))
            painter.drawRoundedRect(node, 13, 13)
            if index == 0:
                self._draw_worker(painter, center_x, center_y)
            elif index == 1:
                self._draw_product(painter, center_x, center_y)
            elif index == 2:
                self._draw_steps(painter, center_x, center_y)
            else:
                self._draw_quality(painter, center_x, center_y)

            painter.setPen(QColor("#344658"))
            painter.setFont(QFont("Malgun Gothic", 9, QFont.DemiBold))
            painter.drawText(
                QRectF(center_x - 43, center_y + 39, 86, 24),
                Qt.AlignHCenter | Qt.AlignTop,
                self.LABELS[index],
            )

    @staticmethod
    def _icon_pen() -> QPen:
        pen = QPen(QColor("#315E91"), 2.2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen

    def _draw_worker(self, painter: QPainter, x: float, y: float) -> None:
        painter.setPen(self._icon_pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(x - 6, y - 15, 12, 12))
        body = QPainterPath()
        body.moveTo(x - 15, y + 14)
        body.cubicTo(x - 13, y + 2, x + 13, y + 2, x + 15, y + 14)
        painter.drawPath(body)

    def _draw_product(self, painter: QPainter, x: float, y: float) -> None:
        painter.setPen(self._icon_pen())
        painter.setBrush(Qt.NoBrush)
        box = QPolygonF([
            QPointF(x, y - 15), QPointF(x + 15, y - 7),
            QPointF(x + 15, y + 10), QPointF(x, y + 17),
            QPointF(x - 15, y + 10), QPointF(x - 15, y - 7),
        ])
        painter.drawPolygon(box)
        painter.drawLine(QPointF(x - 15, y - 7), QPointF(x, y + 1))
        painter.drawLine(QPointF(x + 15, y - 7), QPointF(x, y + 1))
        painter.drawLine(QPointF(x, y + 1), QPointF(x, y + 17))

    def _draw_steps(self, painter: QPainter, x: float, y: float) -> None:
        painter.setPen(Qt.NoPen)
        for offset, bar_width in ((-11, 19), (0, 27), (11, 35)):
            painter.setBrush(QColor("#315E91"))
            painter.drawRoundedRect(
                QRectF(x - bar_width / 2, y + offset - 3, bar_width, 6), 3, 3
            )

    def _draw_quality(self, painter: QPainter, x: float, y: float) -> None:
        painter.setPen(self._icon_pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(x - 16, y - 16, 32, 32))
        check = QPainterPath()
        check.moveTo(x - 8, y)
        check.lineTo(x - 2, y + 7)
        check.lineTo(x + 10, y - 7)
        painter.drawPath(check)


class LoginWindow(QMainWindow):
    """관리자 ID와 해시 비밀번호를 확인하는 첫 화면입니다."""

    login_succeeded = pyqtSignal(dict)

    def __init__(self, database_manager: DatabaseManager):
        super().__init__()
        self.database_manager = database_manager
        self.setWindowTitle("Team STEP · 로그인")
        self.setMinimumSize(900, 560)
        self.resize(980, 620)
        self._create_ui()

    def _create_ui(self) -> None:
        """브랜드 패널과 로그인 카드를 구성합니다."""
        brand_panel = QFrame()
        brand_panel.setObjectName("brandPanel")
        brand_panel.setStyleSheet(
            "QFrame#brandPanel {"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #F3F7FB,stop:0.48 #E5EEF7,stop:1 #CFDFEE);"
            "border:1px solid #C8D7E5;border-radius:12px;"
            "}"
        )
        brand_panel.setMinimumWidth(420)
        brand_layout = QVBoxLayout(brand_panel)
        brand_layout.setContentsMargins(42, 42, 42, 42)
        brand_layout.setSpacing(16)

        logo_row = QHBoxLayout()
        logo_mark = QLabel("S")
        logo_mark.setFixedSize(44, 44)
        logo_mark.setAlignment(Qt.AlignCenter)
        logo_mark.setStyleSheet(
            "color:#FFFFFF; background:#315E91; border-radius:10px; "
            "font-size:16px; font-weight:900;"
        )
        logo_name = QLabel("Team STEP")
        logo_name.setStyleSheet("font-size:16px; font-weight:800; color:#263442;")
        logo_row.addWidget(logo_mark)
        logo_row.addWidget(logo_name)
        logo_row.addStretch()
        brand_layout.addLayout(logo_row)
        brand_layout.addSpacing(32)

        eyebrow = QLabel("SEQUENTIAL TRACKING & ERROR PREVENTION")
        eyebrow.setObjectName("eyebrow")
        brand_title = QLabel("생산 공정 모니터링 시스템")
        brand_title.setStyleSheet("font-size:27px; font-weight:800; color:#1F2C39;")
        brand_description = QLabel("작업 현황과 품질 데이터를\n한곳에서 관리합니다.")
        brand_description.setObjectName("subtitle")
        brand_description.setStyleSheet("color:#637384; line-height:1.5;")
        brand_layout.addWidget(eyebrow)
        brand_layout.addWidget(brand_title)
        brand_layout.addWidget(brand_description)
        brand_layout.addSpacing(20)
        brand_layout.addWidget(ProcessFlowIllustration())
        brand_layout.addStretch()
        team_signature = QLabel("Team STEP  ·  Monitoring PC")
        team_signature.setStyleSheet("color:#708090;font-size:11px;font-weight:700;")
        brand_layout.addWidget(team_signature)

        login_card = QFrame()
        login_card.setObjectName("card")
        login_card.setFixedWidth(390)
        add_card_shadow(login_card)
        card_layout = QVBoxLayout(login_card)
        card_layout.setContentsMargins(38, 38, 38, 38)
        card_layout.setSpacing(10)

        card_eyebrow = QLabel("관리자 전용")
        card_eyebrow.setObjectName("eyebrow")
        title_label = QLabel("관리자 로그인")
        title_label.setObjectName("pageTitle")
        subtitle_label = QLabel("승인된 관리자 계정으로 접속해 주세요.")
        subtitle_label.setObjectName("subtitle")
        card_layout.addWidget(card_eyebrow)
        card_layout.addWidget(title_label)
        card_layout.addWidget(subtitle_label)
        card_layout.addSpacing(22)

        id_label = QLabel("관리자 ID")
        id_label.setStyleSheet("font-weight:600;")
        self.employee_id_input = QLineEdit()
        self.employee_id_input.setPlaceholderText("관리자 ID 입력")
        self.employee_id_input.setClearButtonEnabled(True)
        password_label = QLabel("비밀번호")
        password_label.setStyleSheet("font-weight:600;")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("비밀번호 입력")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.try_login)
        card_layout.addWidget(id_label)
        card_layout.addWidget(self.employee_id_input)
        card_layout.addSpacing(7)
        card_layout.addWidget(password_label)
        card_layout.addWidget(self.password_input)

        self.error_label = QLabel("")
        self.error_label.setMinimumHeight(34)
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color:#FF7D8A; font-size:12px;")
        card_layout.addWidget(self.error_label)

        login_button = QPushButton("로그인")
        login_button.setObjectName("primaryButton")
        login_button.setMinimumHeight(46)
        login_button.setDefault(True)
        login_button.clicked.connect(self.try_login)
        card_layout.addWidget(login_button)
        card_layout.addStretch()
        security_label = QLabel("안전한 비밀번호 암호화가 적용되어 있습니다.")
        security_label.setAlignment(Qt.AlignCenter)
        security_label.setObjectName("mutedText")
        security_label.setStyleSheet("font-size:10px; color:#8A96A3;")
        card_layout.addWidget(security_label)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(34, 34, 34, 34)
        content_layout.setSpacing(28)
        content_layout.addWidget(brand_panel, 1)
        content_layout.addWidget(login_card)
        root = QWidget()
        root.setLayout(content_layout)
        self.setCentralWidget(root)
        self.employee_id_input.setFocus()

    def try_login(self) -> None:
        """DB에서 관리자 권한과 해시 비밀번호를 검증합니다."""
        employee_id = self.employee_id_input.text().strip()
        password = self.password_input.text()
        if not employee_id or not password:
            self.error_label.setText("관리자 ID와 비밀번호를 모두 입력하세요.")
            return
        try:
            admin_info = self.database_manager.verify_admin_login(employee_id, password)
        except Exception as error:
            QMessageBox.critical(self, "DB 오류", f"로그인 확인 중 오류가 발생했습니다.\n{error}")
            return
        if admin_info is None:
            self.error_label.setText("계정 정보가 올바르지 않거나 관리자 권한이 없습니다.")
            self.password_input.clear()
            self.password_input.setFocus()
            return
        self.error_label.clear()
        self.login_succeeded.emit(admin_info)
