"""제품 작업 회차의 STEP 작업시간을 보여주는 Dialog입니다."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from db.database_manager import DatabaseManager
from ui.ui_helpers import fill_table, make_read_only_table


class StepHistoryDialog(QDialog):
    """선택한 제품 작업 회차의 STEP 작업시간을 조회합니다."""

    step_selected = pyqtSignal(int)

    # 하위 호환성을 위한 헬퍼 바인딩
    _make_table = staticmethod(make_read_only_table)
    _fill_table = staticmethod(fill_table)

    def __init__(self, product_run: dict, database_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.product_run = product_run
        self.database_manager = database_manager
        self.setWindowTitle("Team STEP · STEP 작업시간")
        self.setMinimumSize(900, 600)
        self.resize(1060, 700)
        self._create_ui()
        self.load_steps()

    def _create_ui(self) -> None:
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        eyebrow = QLabel("제품 작업 기록")
        eyebrow.setObjectName("eyebrow")
        title = QLabel(f"{self.product_run['product_name']} · STEP 작업시간")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            f"제품번호  {self.product_run['product_id']}  ·  "
            f"작업 시작  {self.product_run['started_at']}"
        )
        subtitle.setObjectName("subtitle")
        header_text.addWidget(eyebrow)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        close_button = QPushButton("닫기")
        close_button.setObjectName("ghostButton")
        close_button.clicked.connect(self.accept)
        header.addLayout(header_text)
        header.addStretch()
        header.addWidget(close_button, alignment=Qt.AlignTop)

        self.step_table = self._make_table(
            ["STEP", "STEP 시작시간", "STEP 완료시간", "실제 작업시간",
             "PASS", "FAIL", "FAIL률"]
        )
        step_header = self.step_table.horizontalHeader()
        for column in (0, 3, 4, 5, 6):
            step_header.setSectionResizeMode(column, QHeaderView.Fixed)
        step_header.setSectionResizeMode(1, QHeaderView.Stretch)
        step_header.setSectionResizeMode(2, QHeaderView.Stretch)
        for column, width in {0: 64, 3: 112, 4: 66, 5: 66, 6: 72}.items():
            self.step_table.setColumnWidth(column, width)
        self.step_table.itemSelectionChanged.connect(self.emit_selected_step)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)
        layout.addLayout(header)
        layout.addWidget(self.step_table, 1)

    def load_steps(self) -> None:
        """제품 작업 회차의 STEP 기록을 불러옵니다."""
        try:
            step_runs = self.database_manager.get_step_runs(
                self.product_run["product_run_id"]
            )
            self._fill_table(
                self.step_table,
                [[item["step_no"], item["started_at"], item["completed_at"],
                  self.database_manager.format_seconds(item["actual_seconds"]),
                  item["pass_count"], item["fail_count"],
                  f"{float(item['fail_rate']):.1f}%"] for item in step_runs],
            )
            for row_index, step_run in enumerate(step_runs):
                self.step_table.item(row_index, 0).setData(
                    Qt.UserRole, step_run["step_run_id"]
                )
                if step_run["fail_count"]:
                    self.step_table.item(row_index, 5).setForeground(QColor("#B45656"))
                    self.step_table.item(row_index, 6).setForeground(QColor("#B45656"))
            if step_runs:
                self.step_table.selectRow(0)
        except Exception as error:
            QMessageBox.critical(self, "DB 오류", f"STEP 조회 중 오류가 발생했습니다.\n{error}")

    def current_step_run_id(self):
        """현재 선택된 STEP 작업 ID를 반환합니다."""
        row = self.step_table.currentRow()
        if row < 0 or self.step_table.item(row, 0) is None:
            return None
        return self.step_table.item(row, 0).data(Qt.UserRole)

    def emit_selected_step(self) -> None:
        """선택한 STEP을 직원 상세의 일시정지 이력에 전달합니다."""
        step_run_id = self.current_step_run_id()
        if step_run_id is not None:
            self.step_selected.emit(int(step_run_id))
