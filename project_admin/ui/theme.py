"""Monitoring PC 전체에서 사용하는 밝고 차분한 업무용 테마입니다."""

from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtWidgets import QApplication, QGraphicsDropShadowEffect, QWidget


COLORS = {
    "background": "#F3F5F8",
    "surface": "#FFFFFF",
    "surface_light": "#F8FAFC",
    "border": "#DDE3EA",
    "primary": "#315E91",
    "primary_dark": "#244A75",
    "text": "#202936",
    "muted": "#6F7B89",
    "danger": "#B64A4A",
    "warning": "#A87522",
}


APP_STYLE = """
QWidget {
    color: #202936;
    font-family: "Pretendard", "Malgun Gothic", "Segoe UI";
    font-size: 13px;
}
QMainWindow, QDialog { background-color: #F3F5F8; }
QLabel#eyebrow { color: #58789C; font-size: 11px; font-weight: 700; }
QLabel#pageTitle { color: #18212C; font-size: 24px; font-weight: 700; }
QLabel#sectionTitle { color: #202936; font-size: 15px; font-weight: 700; }
QLabel#subtitle, QLabel#mutedText { color: #6F7B89; }
QLabel#metricValue { color: #202936; font-size: 22px; font-weight: 700; }
QLabel#metricLabel { color: #778391; font-size: 11px; }
QFrame#card, QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #DDE3EA;
    border-radius: 9px;
}
QFrame#topBar { background-color: #FFFFFF; border-bottom: 1px solid #DDE3EA; }
QFrame#navigationBar { background-color: #FFFFFF; border-bottom: 1px solid #DDE3EA; }
QFrame#brandPanel {
    background-color: #E9EFF6;
    border: 1px solid #D4DEE9;
    border-radius: 12px;
}
QFrame#accentLine { background-color: #315E91; border-radius: 2px; }
QLineEdit, QSpinBox, QTextEdit {
    min-height: 40px;
    padding: 0 13px;
    color: #202936;
    background-color: #FFFFFF;
    border: 1px solid #C9D2DC;
    border-radius: 6px;
    selection-background-color: #B9CCE2;
}
QLineEdit:hover, QSpinBox:hover, QTextEdit:hover { border-color: #9EABB9; }
QLineEdit:focus, QSpinBox:focus, QTextEdit:focus { border: 1px solid #315E91; background-color: #FFFFFF; }
QLineEdit:read-only { color:#526170; background:#F3F5F8; border-color:#E0E5EA; }
QPushButton {
    min-height: 38px;
    padding: 0 17px;
    color: #33404D;
    background-color: #FFFFFF;
    border: 1px solid #C9D2DC;
    border-radius: 6px;
    font-weight: 600;
}
QPushButton:hover { background-color: #F1F5F9; border-color: #9EABB9; }
QPushButton:pressed { background-color: #E6EBF0; }
QPushButton#primaryButton {
    color: #FFFFFF;
    background-color: #315E91;
    border: 1px solid #315E91;
    font-weight: 700;
}
QPushButton#primaryButton:hover { background-color: #284F7B; border-color: #284F7B; }
QPushButton#primaryButton:pressed { background-color: #203F63; }
QPushButton#ghostButton { background-color: transparent; border-color: #C9D2DC; }
QPushButton#dangerButton { color: #A04444; background-color: #FFFFFF; border-color: #DFC3C3; }
QPushButton#dangerButton:hover { color: #8E3434; background-color: #FFF4F4; }
QPushButton#navButton {
    min-width: 125px;
    color: #5E6B78;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
}
QPushButton#navButton:hover { color:#315E91; background-color:#F1F5F9; }
QPushButton#navButton:checked {
    color:#244A75;
    background-color:#EAF1F8;
    border:1px solid #C9D9E9;
    font-weight:700;
}
QTableWidget {
    color: #2D3742;
    background-color: #FFFFFF;
    alternate-background-color: #F8FAFC;
    border: 1px solid #DDE3EA;
    border-radius: 7px;
    gridline-color: transparent;
    outline: none;
    selection-background-color: #DCE8F5;
    selection-color: #183B62;
}
QTableWidget::item { min-height: 40px; padding: 6px 10px; border-bottom: 1px solid #E8EDF2; }
QTableWidget::item:hover { background-color: #EFF4F9; }
QHeaderView::section {
    min-height: 38px;
    padding: 6px 10px;
    color: #596675;
    background-color: #F2F5F8;
    border: none;
    border-bottom: 1px solid #D7DFE7;
    font-size: 11px;
    font-weight: 700;
}
QScrollBar:vertical { width: 10px; background: #F4F6F8; margin: 2px; }
QScrollBar::handle:vertical { background: #BCC6D0; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTabWidget::pane { border: 1px solid #DDE3EA; background-color: #FFFFFF; border-radius: 8px; top: -1px; }
QTabBar::tab {
    min-width: 140px;
    min-height: 38px;
    padding: 0 14px;
    color: #707C89;
    background: transparent;
    border-bottom: 2px solid transparent;
    font-weight: 600;
}
QTabBar::tab:selected { color: #315E91; border-bottom: 2px solid #315E91; }
QTabBar::tab:hover { color: #283F59; }
QSplitter::handle { background-color: #E1E6EC; width: 2px; height: 2px; }
QToolTip { color: #202936; background-color: #FFFFFF; border: 1px solid #BFC9D3; padding: 6px; }
QMessageBox { background-color: #FFFFFF; }
"""


def apply_theme(application: QApplication) -> None:
    """애플리케이션 전체에 폰트, 팔레트, 스타일을 적용합니다."""
    application.setFont(QFont("Malgun Gothic", 10))
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS["background"]))
    palette.setColor(QPalette.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.Base, QColor(COLORS["surface"]))
    palette.setColor(QPalette.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.Button, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ButtonText, QColor(COLORS["text"]))
    palette.setColor(QPalette.Highlight, QColor("#DCE8F5"))
    palette.setColor(QPalette.HighlightedText, QColor("#183B62"))
    application.setPalette(palette)
    application.setStyleSheet(APP_STYLE)


def add_card_shadow(widget: QWidget, blur_radius: int = 24) -> None:
    """카드가 배경과 자연스럽게 구분되도록 옅은 그림자를 적용합니다."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur_radius)
    shadow.setOffset(0, 5)
    shadow.setColor(QColor(35, 49, 65, 32))
    widget.setGraphicsEffect(shadow)
