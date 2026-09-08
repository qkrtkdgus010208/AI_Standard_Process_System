"""관리자 프로그램의 공통 UI 헬퍼 및 재사용 컴포넌트 모듈입니다.

테이블 생성/데이터 바인딩, 메트릭 카드 UI 위젯, 공통 역할 명칭 매핑 등을 제공합니다.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QFrame, QHeaderView, QLabel,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

ROLE_DISPLAY_NAMES: dict[str, str] = {
    "admin": "관리자",
    "worker": "작업자",
}


def make_read_only_table(headers: list[str]) -> QTableWidget:
    """헤더 목록으로 읽기 전용 단일 행 선택 QTableWidget을 생성합니다."""
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(42)
    header = table.horizontalHeader()
    for column in range(len(headers)):
        header.setSectionResizeMode(column, QHeaderView.Stretch)
    return table


def fill_table(table: QTableWidget, rows: list[list]) -> None:
    """QTableWidget의 내용을 주어진 2차원 데이터 행으로 안전하게 채웁니다."""
    table.blockSignals(True)
    table.clearContents()
    table.setRowCount(len(rows))
    for row_index, values in enumerate(rows):
        for column_index, value in enumerate(values):
            display = "—" if value is None or value == "" else str(value)
            item = QTableWidgetItem(display)
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row_index, column_index, item)
    table.blockSignals(False)


def create_metric_card(
    label_text: str,
    initial_value: str = "0",
    accent_color: str = "#315E91",
) -> tuple[QFrame, QLabel]:
    """라벨과 강조 색상 숫자 값을 가진 통계/메트릭 카드 위젯을 생성합니다."""
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(4)

    title = QLabel(label_text)
    title.setObjectName("mutedText")
    title.setStyleSheet("font-size:11px;")

    value_label = QLabel(initial_value)
    value_label.setStyleSheet(
        f"font-size:24px; font-weight:800; color:{accent_color};"
    )

    layout.addWidget(title)
    layout.addWidget(value_label)
    return card, value_label
