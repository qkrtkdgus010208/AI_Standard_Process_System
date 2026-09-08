"""관리자 프로그램과 통일된 밝은 업무용 PyQt 테마입니다."""

from PyQt5.QtGui import QColor, QFont, QPalette
from PyQt5.QtWidgets import QApplication


APP_STYLE = """
QWidget { color:#202936; font-family:"Pretendard","Malgun Gothic","Segoe UI"; font-size:13px; }
QMainWindow, QDialog { background:#F3F5F8; }
QLabel#pageTitle { color:#18212C; font-size:23px; font-weight:700; }
QLabel#sectionTitle { color:#202936; font-size:15px; font-weight:700; }
QLabel#subtitle, QLabel#mutedText { color:#6F7B89; }
QLabel#smallLabel { color:#778391; font-size:11px; }
QFrame#topBar { background:#FFFFFF; border-bottom:1px solid #DDE3EA; }
QFrame#card { background:#FFFFFF; border:1px solid #DDE3EA; border-radius:9px; }
QFrame#callBanner { background:#FFF8E8; border:1px solid #E8CF91; border-radius:8px; }
QLineEdit, QSpinBox, QComboBox {
    min-height:38px; padding:0 12px; color:#202936; background:#FFFFFF;
    border:1px solid #C9D2DC; border-radius:6px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border:1px solid #315E91; }
QLineEdit:read-only { color:#526170; background:#F3F5F8; border-color:#E0E5EA; }
QComboBox:disabled { color:#9AA8B6; background:#E9ECEF; border-color:#D5DCE3; }
QComboBox::drop-down { border:none; width:26px; }
QComboBox QAbstractItemView {
    background:#FFFFFF; border:1px solid #C9D2DC; selection-background-color:#DCE8F5; selection-color:#183B62;
}
QPushButton {
    min-height:38px; padding:0 16px; color:#263442; background:#FFFFFF;
    border:1px solid #BCC8D4; border-radius:6px; font-weight:600;
}
QPushButton:hover { background:#EEF3F8; border-color:#93A6B8; }
QPushButton#primaryButton { color:#FFFFFF; background:#2A6096; border:1px solid #245281; font-weight:700; }
QPushButton#primaryButton:hover { background:#1F4D7B; }
QPushButton#successButton { color:#FFFFFF; background:#2D7D4B; border:1px solid #23683D; font-weight:700; }
QPushButton#successButton:hover { background:#23683D; }
QPushButton#dangerButton { color:#FFFFFF; background:#C93B3B; border:1px solid #B02F2F; font-weight:700; }
QPushButton#dangerButton:hover { background:#AA2A2A; }
QPushButton#warningButton { color:#6E4B14; background:#FFE8B3; border:1px solid #DFB96C; font-weight:700; }
QPushButton#warningButton:hover { background:#FFDE94; }
QPushButton:disabled,
QPushButton#primaryButton:disabled,
QPushButton#dangerButton:disabled,
QPushButton#warningButton:disabled,
QPushButton#successButton:disabled {
    color: #9AA8B6;
    background: #E9ECEF;
    border: 1px solid #D5DCE3;
    font-weight: 500;
}
QListWidget {
    color:#354250; background:#FFFFFF; alternate-background-color:#F8FAFC;
    border:1px solid #DDE3EA; border-radius:7px; outline:none;
}
QListWidget::item { min-height:30px; padding:4px 8px; border-bottom:1px solid #EEF1F4; }
QProgressBar {
    min-height:18px; color:#33404D; background:#E7ECF1; border:none;
    border-radius:9px; text-align:center; font-size:11px;
}
QProgressBar::chunk { background:#4778AA; border-radius:9px; }
QToolTip { color:#202936; background:#FFFFFF; border:1px solid #BFC9D3; padding:6px; }
QMessageBox { background:#FFFFFF; }
"""


def apply_theme(application: QApplication) -> None:
    """작업자 애플리케이션 전체에 공통 테마를 적용합니다."""
    application.setFont(QFont("Malgun Gothic", 10))
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#F3F5F8"))
    palette.setColor(QPalette.WindowText, QColor("#202936"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.Text, QColor("#202936"))
    palette.setColor(QPalette.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ButtonText, QColor("#202936"))
    palette.setColor(QPalette.Highlight, QColor("#DCE8F5"))
    palette.setColor(QPalette.HighlightedText, QColor("#183B62"))
    application.setPalette(palette)
    application.setStyleSheet(APP_STYLE)
