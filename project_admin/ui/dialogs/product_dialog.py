"""제품 등록과 STEP별 기준 이미지 설정을 위한 관리자 Dialog입니다."""

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)


class ProductDialog(QDialog):
    """제품 기본정보와 각 STEP의 정상 예시 이미지를 입력받습니다."""

    def __init__(self, product=None, parent=None):
        super().__init__(parent)
        self.product = product
        self._step_image_paths = {
            int(step): str(path)
            for step, path in (product or {}).get("step_images", {}).items()
            if path
        }
        self._step_rows = {}
        self.setWindowTitle("제품 수정" if product else "제품 등록")
        self.setMinimumSize(700, 640)
        self.resize(760, 760)
        self._create_ui()

    def _create_ui(self) -> None:
        title = QLabel("제품 정보 수정" if self.product else "새 제품 등록")
        title.setObjectName("pageTitle")
        subtitle = QLabel("제품 정보와 각 STEP에서 완성되어야 할 기준 이미지를 설정하세요.")
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

        guide_title = QLabel("STEP별 기준 이미지")
        guide_title.setObjectName("sectionTitle")
        guide_help = QLabel("JPG·PNG 등 이미지 파일을 선택하세요. 저장 시 1280×720 이내로 자동 변환됩니다.")
        guide_help.setObjectName("mutedText")
        guide_help.setWordWrap(True)

        self.guide_container = QWidget()
        self.guide_layout = QVBoxLayout(self.guide_container)
        self.guide_layout.setContentsMargins(0, 0, 0, 0)
        self.guide_layout.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.guide_container)
        scroll.setMinimumHeight(300)

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
        layout.addSpacing(6)
        layout.addLayout(form)
        layout.addSpacing(8)
        layout.addWidget(guide_title)
        layout.addWidget(guide_help)
        layout.addWidget(scroll, 1)
        layout.addLayout(buttons)

        self.total_steps_input.valueChanged.connect(self._rebuild_step_rows)
        self._rebuild_step_rows()

    def _rebuild_step_rows(self) -> None:
        while self.guide_layout.count():
            item = self.guide_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._step_rows.clear()
        for step_no in range(1, self.total_steps_input.value() + 1):
            row = QFrame()
            row.setObjectName("card")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)

            step_label = QLabel(f"STEP {step_no}")
            step_label.setMinimumWidth(72)
            step_label.setStyleSheet("font-weight:700; color:#315E91;")
            preview = QLabel("이미지 없음")
            preview.setAlignment(Qt.AlignCenter)
            preview.setFixedSize(128, 76)
            preview.setStyleSheet(
                "color:#7B8794; background:#F4F6F8; border:1px solid #DDE3EA; border-radius:5px;"
            )
            file_label = QLabel()
            file_label.setWordWrap(True)
            choose_button = QPushButton("사진 선택")
            remove_button = QPushButton("삭제")
            choose_button.clicked.connect(
                lambda _checked=False, number=step_no: self._choose_image(number)
            )
            remove_button.clicked.connect(
                lambda _checked=False, number=step_no: self._remove_image(number)
            )

            text_layout = QVBoxLayout()
            text_layout.addWidget(file_label)
            button_layout = QHBoxLayout()
            button_layout.addWidget(choose_button)
            button_layout.addWidget(remove_button)
            button_layout.addStretch()
            text_layout.addLayout(button_layout)
            row_layout.addWidget(step_label)
            row_layout.addWidget(preview)
            row_layout.addLayout(text_layout, 1)
            self.guide_layout.addWidget(row)
            self._step_rows[step_no] = (preview, file_label, remove_button)
            self._refresh_step_row(step_no)
        self.guide_layout.addStretch()

    def _choose_image(self, step_no: int) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, f"STEP {step_no} 기준 이미지 선택", "",
            "이미지 파일 (*.jpg *.jpeg *.png *.bmp *.webp);;모든 파일 (*)",
        )
        if path:
            self._step_image_paths[step_no] = path
            self._refresh_step_row(step_no)

    def _remove_image(self, step_no: int) -> None:
        self._step_image_paths.pop(step_no, None)
        self._refresh_step_row(step_no)

    def _refresh_step_row(self, step_no: int) -> None:
        preview, file_label, remove_button = self._step_rows[step_no]
        path = self._step_image_paths.get(step_no, "")
        pixmap = QPixmap(path) if path else QPixmap()
        if not pixmap.isNull():
            preview.setPixmap(
                pixmap.scaled(preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            file_label.setText(Path(path).name)
            file_label.setToolTip(path)
            remove_button.setEnabled(True)
        else:
            preview.clear()
            preview.setText("이미지 없음")
            file_label.setText("선택되지 않음")
            file_label.setToolTip("")
            remove_button.setEnabled(False)

    def _validate_and_accept(self) -> None:
        if not self.product_id_input.text().strip():
            self.product_id_input.setFocus()
            return
        if not self.product_name_input.text().strip():
            self.product_name_input.setFocus()
            return
        self.accept()

    def get_product_data(self) -> dict:
        """입력된 제품 데이터와 현재 STEP 이미지 선택을 반환합니다."""
        total_steps = self.total_steps_input.value()
        return {
            "product_id": self.product_id_input.text().strip(),
            "product_name": self.product_name_input.text().strip(),
            "total_steps": total_steps,
            "step_images": {
                step: path for step, path in self._step_image_paths.items()
                if 1 <= step <= total_steps and path
            },
        }
