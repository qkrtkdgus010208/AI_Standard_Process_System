"""제품 등록과 수정을 위한 관리자 Dialog입니다."""

from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QVBoxLayout,
)


class ProductDialog(QDialog):
    """제품번호, 제품명, 전체 STEP을 입력받습니다."""

    def __init__(self, product=None, parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle("제품 수정" if product else "제품 등록")
        self.setFixedSize(430, 310)
        self._create_ui()

    def _create_ui(self) -> None:
        title = QLabel("제품 정보 수정" if self.product else "새 제품 등록")
        title.setObjectName("pageTitle")
        subtitle = QLabel("제품번호와 공정에 필요한 전체 STEP을 설정하세요.")
        subtitle.setObjectName("subtitle")
        self.product_id_input = QLineEdit()
        self.product_id_input.setPlaceholderText("예: P001")
        self.product_name_input = QLineEdit()
        self.product_name_input.setPlaceholderText("제품명")
        self.total_steps_input = QSpinBox()
        self.total_steps_input.setRange(1, 999)
        self.total_steps_input.setValue(1)
        if self.product:
            self.product_id_input.setText(self.product["product_id"])
            self.product_id_input.setReadOnly(True)
            self.product_name_input.setText(self.product["product_name"])
            self.total_steps_input.setValue(int(self.product["total_steps"]))
        form = QFormLayout()
        form.setSpacing(12)
        form.addRow("제품번호", self.product_id_input)
        form.addRow("제품명", self.product_name_input)
        form.addRow("전체 STEP", self.total_steps_input)
        cancel_button = QPushButton("취소")
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("저장")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._validate_and_accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
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
        """필수 입력값이 채워진 경우에만 Dialog를 닫습니다."""
        if not self.product_id_input.text().strip():
            self.product_id_input.setFocus()
            return
        if not self.product_name_input.text().strip():
            self.product_name_input.setFocus()
            return
        self.accept()

    def get_product_data(self) -> dict:
        """입력된 제품 데이터를 반환합니다."""
        return {
            "product_id": self.product_id_input.text().strip(),
            "product_name": self.product_name_input.text().strip(),
            "total_steps": self.total_steps_input.value(),
        }
