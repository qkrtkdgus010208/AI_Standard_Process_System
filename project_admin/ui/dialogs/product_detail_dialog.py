"""제품 기본정보와 STEP별 품질 지표를 보여주는 관리자 Dialog입니다."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from db.database_manager import DatabaseManager


class ProductDetailDialog(QDialog):
    """제품의 생산 현황과 STEP별 검사·불량 정보를 한 표로 제공합니다."""

    def __init__(self, product: dict, database_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.product = product
        self.database_manager = database_manager
        self.setWindowTitle("제품 상세 정보")
        self.setMinimumSize(980, 660)
        self.resize(1060, 740)
        self._create_ui()
        self.load_data()

    @staticmethod
    def _metric_card(caption: str, color: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 13, 18, 13)
        layout.setSpacing(3)
        value = QLabel("0")
        value.setStyleSheet(f"color:{color};font-size:22px;font-weight:800;")
        label = QLabel(caption)
        label.setObjectName("metricLabel")
        layout.addWidget(value)
        layout.addWidget(label)
        return card, value

    def _create_ui(self) -> None:
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        eyebrow = QLabel("PRODUCT QUALITY  ·  DETAIL")
        eyebrow.setObjectName("eyebrow")
        title = QLabel(self.product["product_name"])
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            f"제품번호  {self.product['product_id']}  ·  전체 {self.product['total_steps']} STEP"
        )
        subtitle.setObjectName("subtitle")
        header_text.addWidget(eyebrow)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        close_button = QPushButton("닫기")
        close_button.clicked.connect(self.accept)
        reset_button = QPushButton("품질 집계 초기화")
        reset_button.setObjectName("dangerButton")
        reset_button.setToolTip("과거 이력은 보존하고 현재 시점부터 품질 통계를 새로 집계합니다.")
        reset_button.clicked.connect(self.reset_quality_data)
        header.addLayout(header_text)
        header.addStretch()
        header.addWidget(reset_button, alignment=Qt.AlignTop)
        header.addWidget(close_button, alignment=Qt.AlignTop)

        baseline_bar = QFrame()
        baseline_bar.setObjectName("brandPanel")
        baseline_layout = QHBoxLayout(baseline_bar)
        baseline_layout.setContentsMargins(16, 10, 16, 10)
        baseline_title = QLabel("분석 기준")
        baseline_title.setStyleSheet("color:#315E91;font-weight:700;")
        self.baseline_label = QLabel("전체 기간")
        self.baseline_label.setStyleSheet("color:#526170;")
        baseline_note = QLabel("이전 기록은 보존되며 현재 통계에서만 제외됩니다.")
        baseline_note.setObjectName("subtitle")
        baseline_layout.addWidget(baseline_title)
        baseline_layout.addSpacing(6)
        baseline_layout.addWidget(self.baseline_label)
        baseline_layout.addStretch()
        baseline_layout.addWidget(baseline_note)

        step_card, self.step_value = self._metric_card("전체 STEP", "#315E91")
        complete_card, self.complete_value = self._metric_card("완료 제품", "#2F7D4A")
        fail_card, self.fail_value = self._metric_card("검사 FAIL", "#B45656")
        defect_card, self.defect_value = self._metric_card("불량 버튼", "#A87522")
        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        for column, card in enumerate((step_card, complete_card, fail_card, defect_card)):
            metrics.addWidget(card, 0, column)

        table_card = QFrame()
        table_card.setObjectName("card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 15, 18, 18)
        table_title = QLabel("STEP별 품질 현황")
        table_title.setObjectName("sectionTitle")
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["STEP", "전체 판정", "PASS", "FAIL", "FAIL률",
             "불량 버튼", "최근 이상 발생", "분석"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        table_header = self.table.horizontalHeader()
        for column in range(6):
            table_header.setSectionResizeMode(column, QHeaderView.Fixed)
        table_header.setSectionResizeMode(6, QHeaderView.Stretch)
        table_header.setSectionResizeMode(7, QHeaderView.Fixed)
        for column, width in enumerate((85, 95, 80, 80, 85, 95)):
            self.table.setColumnWidth(column, width)
        self.table.setColumnWidth(7, 110)
        table_layout.addWidget(table_title)
        table_layout.addWidget(self.table, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 26)
        layout.setSpacing(14)
        layout.addLayout(header)
        layout.addWidget(baseline_bar)
        layout.addLayout(metrics)
        layout.addWidget(table_card, 1)

    def load_data(self) -> None:
        baseline = self.database_manager.get_product_quality_baseline(
            self.product["product_id"]
        )
        self.baseline_label.setText(
            f"{baseline['reset_at']} 이후" if baseline else "전체 기간"
        )
        product_overview = next(
            (
                item for item in self.database_manager.search_products(self.product["product_id"])
                if item["product_id"] == self.product["product_id"]
            ),
            {},
        )
        rows = self.database_manager.get_product_step_quality_summary(
            self.product["product_id"]
        )
        total_fail = sum(int(row["fail_count"]) for row in rows)
        total_defect_buttons = sum(int(row["defect_button_count"]) for row in rows)
        self.step_value.setText(str(self.product["total_steps"]))
        self.complete_value.setText(str(product_overview.get("completed_count", 0)))
        self.fail_value.setText(str(total_fail))
        self.defect_value.setText(str(total_defect_buttons))

        highest_fail = max((int(row["fail_count"]) for row in rows), default=0)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            fail_count = int(row["fail_count"])
            defect_count = int(row["defect_button_count"])
            if defect_count > 0:
                analysis, analysis_color = "불량 발생", "#B45656"
            elif highest_fail > 0 and fail_count == highest_fail:
                analysis, analysis_color = "우선 점검", "#B45656"
            elif fail_count > 0:
                analysis, analysis_color = "관찰", "#A87522"
            elif int(row["judgement_count"]) > 0:
                analysis, analysis_color = "양호", "#2F7D4A"
            else:
                analysis, analysis_color = "데이터 없음", "#778391"
            issue_times = [
                value for value in (row["latest_fail_at"], row["latest_defect_at"])
                if value
            ]
            latest_issue = max(issue_times) if issue_times else "—"
            values = (
                f"STEP {row['step_no']}", row["judgement_count"], row["pass_count"],
                fail_count, f"{float(row['fail_rate']):.1f}%", defect_count,
                latest_issue, analysis,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter)
                if column in (3, 4) and fail_count:
                    item.setForeground(QColor("#B45656"))
                elif column == 5 and defect_count:
                    item.setForeground(QColor("#B45656"))
                elif column == 7:
                    item.setForeground(QColor(analysis_color))
                self.table.setItem(row_index, column, item)

    def reset_quality_data(self) -> None:
        """확인 후 현재 시점을 제품 품질 통계의 새 기준으로 설정합니다."""
        answer = QMessageBox.question(
            self,
            "품질 집계 초기화",
            f"{self.product['product_name']} ({self.product['product_id']})의 품질 통계를 "
            "현재 시점부터 새로 집계하시겠습니까?\n\n"
            "현재 화면의 완료·불량률·PASS/FAIL·불량 버튼 수는 0으로 초기화됩니다.\n"
            "과거 원본 작업 및 판정 이력은 삭제되지 않습니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            reset_at = self.database_manager.reset_product_quality_baseline(
                self.product["product_id"]
            )
            self.load_data()
        except Exception as error:
            QMessageBox.warning(self, "초기화 실패", str(error))
            return
        QMessageBox.information(
            self, "초기화 완료",
            f"{reset_at} 이후의 데이터부터 새로 집계합니다.\n과거 이력은 보존되어 있습니다.",
        )
