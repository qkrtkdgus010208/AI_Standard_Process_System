"""직원 상세정보와 호출 기능을 제공하는 Dialog입니다."""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from database_manager import DatabaseManager
from step_history_dialog import StepHistoryDialog
from tcp_client import TcpClient


class EmployeeMessageDialog(QDialog):
    """관리자가 직원에게 보낼 메시지를 작성하는 간단한 Dialog입니다."""

    def __init__(self, employee_id: str, employee_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("직원 메시지 보내기")
        self.setModal(True)
        self.setFixedSize(480, 300)

        title = QLabel("메시지 보내기")
        title.setObjectName("pageTitle")
        target = QLabel(f"받는 직원  ·  {employee_name} ({employee_id})")
        target.setObjectName("subtitle")
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("작업자에게 전달할 내용을 입력하세요.")
        self.message_input.setAcceptRichText(False)

        cancel_button = QPushButton("취소")
        cancel_button.clicked.connect(self.reject)
        send_button = QPushButton("보내기")
        send_button.setObjectName("primaryButton")
        send_button.clicked.connect(self._validate_and_accept)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(cancel_button)
        button_row.addWidget(send_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(target)
        layout.addSpacing(4)
        layout.addWidget(self.message_input, 1)
        layout.addLayout(button_row)
        self.message_input.setFocus()

    def _validate_and_accept(self) -> None:
        """빈 메시지와 지나치게 긴 메시지를 전송 전에 차단합니다."""
        message_text = self.message_text()
        if not message_text:
            QMessageBox.information(self, "메시지 확인", "보낼 메시지를 입력하세요.")
            return
        if len(message_text) > 500:
            QMessageBox.information(self, "메시지 확인", "메시지는 500자 이하로 입력하세요.")
            return
        self.accept()

    def message_text(self) -> str:
        """앞뒤 공백을 제거한 작성 내용을 반환합니다."""
        return self.message_input.toPlainText().strip()


class EmployeeDetailDialog(QDialog):
    """직원의 출퇴근, 제품, STEP, Pause 기록을 조회합니다."""

    def __init__(self, employee_id: str, database_manager: DatabaseManager,
                 tcp_client: TcpClient, parent=None):
        super().__init__(parent)
        self.employee_id = employee_id
        self.database_manager = database_manager
        self.tcp_client = tcp_client
        self.selected_step_run_id = None
        self.setWindowTitle("Team STEP · 직원 상세")
        self.setMinimumSize(1000, 680)
        self.resize(1160, 800)
        self._create_ui()
        self.load_employee_data()

    @staticmethod
    def _make_table(headers: list[str]) -> QTableWidget:
        """조회 전용 테이블을 공통 디자인으로 만듭니다."""
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
        for index in range(len(headers)):
            header.setSectionResizeMode(index, QHeaderView.Stretch)
        return table

    @staticmethod
    def _display(value) -> str:
        """NULL 값을 사용자 친화적인 문자로 표시합니다."""
        return "—" if value is None or value == "" else str(value)

    @staticmethod
    def _table_panel(title: str, table: QTableWidget) -> QFrame:
        """제목과 표만 포함한 간결한 테이블 카드를 만듭니다."""
        panel = QFrame()
        panel.setObjectName("card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        layout.addWidget(table)
        return panel

    @staticmethod
    def _table_tab(table: QTableWidget) -> QWidget:
        """하위 탭에서 표가 전체 공간을 사용하도록 구성합니다."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(table)
        return page

    def _info_value(self, caption: str) -> tuple[QWidget, QLabel]:
        """프로필 카드의 라벨/값 묶음을 만듭니다."""
        caption_label = QLabel(caption)
        caption_label.setObjectName("metricLabel")
        value_label = QLabel("—")
        value_label.setStyleSheet("color:#243241; font-size:15px; font-weight:700;")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(caption_label)
        layout.addWidget(value_label)
        widget = QWidget()
        widget.setLayout(layout)
        return widget, value_label

    def _create_ui(self) -> None:
        """프로필 헤더와 작업 이력 대시보드를 구성합니다."""
        header_row = QHBoxLayout()
        header_text = QVBoxLayout()
        eyebrow = QLabel("직원 정보")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("직원 상세 정보")
        title.setObjectName("pageTitle")
        subtitle = QLabel("출퇴근부터 제품별 STEP 작업시간까지 한 번에 확인합니다.")
        subtitle.setObjectName("subtitle")
        header_text.addWidget(eyebrow)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        close_button = QPushButton("닫기")
        close_button.setObjectName("ghostButton")
        close_button.clicked.connect(self.accept)
        refresh_button = QPushButton("새로고침")
        refresh_button.setToolTip("Gateway에 저장된 최신 작업 이력을 다시 조회합니다.")
        refresh_button.clicked.connect(self.load_employee_data)
        header_row.addLayout(header_text)
        header_row.addStretch()
        header_row.addWidget(refresh_button, alignment=Qt.AlignTop)
        header_row.addWidget(close_button, alignment=Qt.AlignTop)

        profile_card = QFrame()
        profile_card.setObjectName("card")
        profile_layout = QHBoxLayout(profile_card)
        profile_layout.setContentsMargins(22, 18, 22, 18)
        profile_layout.setSpacing(24)
        avatar = QLabel("ID")
        avatar.setFixedSize(58, 58)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            "color:#FFFFFF; background:#315E91; border-radius:12px; "
            "font-size:17px; font-weight:900;"
        )
        employee_widget, self.employee_id_label = self._info_value("직원번호")
        name_widget, self.name_label = self._info_value("이름")
        role_widget, self.role_label = self._info_value("권한")
        profile_layout.addWidget(avatar)
        profile_layout.addWidget(employee_widget, 1)
        profile_layout.addWidget(name_widget, 1)
        profile_layout.addWidget(role_widget, 1)
        profile_layout.addStretch()
        message_button = QPushButton("메시지 보내기")
        message_button.setObjectName("primaryButton")
        message_button.setMinimumWidth(170)
        message_button.setMinimumHeight(46)
        message_button.setToolTip("선택한 직원에게 TCP 메시지를 전송합니다.")
        message_button.clicked.connect(self.send_employee_message)
        profile_layout.addWidget(message_button)

        self.work_table = self._make_table(
            ["로그인 날짜 / 시간", "로그아웃 날짜 / 시간", "근무시간", "근무 판정"]
        )
        work_panel = self._table_panel("최근 출퇴근 기록", self.work_table)
        work_tab = QWidget()
        work_layout = QVBoxLayout(work_tab)
        work_layout.setContentsMargins(14, 14, 14, 14)
        work_layout.addWidget(work_panel)

        self.product_table = self._make_table(
            ["제품 ID", "제품명", "작업 결과", "검사 FAIL", "작업 시작시간", "제품 종료시간"]
        )
        self.product_table.setToolTip(
            "제품 작업 기록을 더블클릭하면 STEP 작업시간을 확인할 수 있습니다."
        )
        self.product_table.itemDoubleClicked.connect(self.open_selected_product_steps)
        self.pause_table = self._make_table(
            ["제품 ID", "제품명", "발생 STEP", "일시정지 시작시간", "작업 재개시간", "일시정지 시간"]
        )
        self.defect_table = self._make_table(
            ["제품 ID", "제품명", "불량 발생 STEP", "유형", "상세", "불량 등록시간"]
        )

        process_tab = QWidget()
        process_layout = QVBoxLayout(process_tab)
        process_layout.setContentsMargins(10, 10, 10, 10)
        self.process_tabs = QTabWidget()
        self.process_tabs.addTab(self._table_tab(self.product_table), "제품 작업 기록")
        self.process_tabs.addTab(self._table_tab(self.pause_table), "일시정지 이력")
        process_layout.addWidget(self.process_tabs)

        defect_tab = QWidget()
        defect_layout = QVBoxLayout(defect_tab)
        defect_layout.setContentsMargins(14, 14, 14, 14)
        defect_layout.addWidget(self._table_panel("불량 이력", self.defect_table))

        tabs = QTabWidget()
        tabs.addTab(process_tab, "공정 작업 이력")
        tabs.addTab(defect_tab, "불량 이력")
        tabs.addTab(work_tab, "출퇴근 기록")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(16)
        layout.addLayout(header_row)
        layout.addWidget(profile_card)
        layout.addWidget(tabs, 1)

    def _fill_table(self, table: QTableWidget, rows: list[list]) -> None:
        """2차원 데이터를 테이블에 안전하게 표시합니다."""
        table.blockSignals(True)
        table.clearContents()
        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(self._display(value))
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row_index, column_index, item)
        table.blockSignals(False)

    def load_employee_data(self) -> None:
        """기본정보, 출퇴근, 전체 제품 작업 기록을 불러옵니다."""
        try:
            employee = self.database_manager.get_employee(self.employee_id)
            if employee is None:
                QMessageBox.warning(self, "조회 실패", "직원 정보를 찾을 수 없습니다.")
                self.reject()
                return
            self.employee_id_label.setText(employee["employee_id"])
            self.name_label.setText(employee["name"])
            self.role_label.setText(
                {"admin": "관리자", "worker": "작업자"}.get(
                    employee["role"], employee["role"] or "—"
                )
            )
            sessions = self.database_manager.get_work_sessions(self.employee_id)
            status_labels = {
                "normal": "●  정상 근무",
                "short": "●  시간 미달",
                "working": "●  근무 중",
            }
            self._fill_table(
                self.work_table,
                [[row["login_at"], row["logout_at"],
                  self.database_manager.format_seconds(row["worked_seconds"]),
                  status_labels.get(row["work_status"], "—")] for row in sessions],
            )
            status_colors = {
                "normal": "#2F7D4A",
                "short": "#B45656",
                "working": "#315E91",
            }
            for row_index, session in enumerate(sessions):
                status_item = self.work_table.item(row_index, 3)
                status_item.setForeground(QColor(status_colors[session["work_status"]]))
            product_runs = self.database_manager.get_product_runs(self.employee_id)
            result_names = {
                "in_progress": "진행 중", "pass": "정상 완료", "defect": "불량 종료",
            }
            self._fill_table(
                self.product_table,
                [[row["product_id"], row["product_name"],
                  result_names.get(row.get("result"), row.get("result") or "—"),
                  row.get("fail_count", 0),
                  row["started_at"], row["completed_at"]] for row in product_runs],
            )
            for row_index, product_run in enumerate(product_runs):
                self.product_table.item(row_index, 0).setData(
                    Qt.UserRole, product_run
                )
                if product_run.get("result") == "defect":
                    self.product_table.item(row_index, 2).setForeground(QColor("#B45656"))
                if product_run.get("fail_count", 0) > 0:
                    self.product_table.item(row_index, 3).setForeground(QColor("#B45656"))

            defect_logs = self.database_manager.get_defect_logs(self.employee_id)
            self._fill_table(
                self.defect_table,
                [[row["product_id"], row["product_name"], f"STEP {row['step_no']}",
                  "수동 불량" if row["defect_type"] == "manual" else row["defect_type"],
                  row["detail"], row["defect_at"]] for row in defect_logs],
            )
            self.load_pause_history()
            if product_runs:
                self.product_table.selectRow(0)
        except Exception as error:
            QMessageBox.critical(self, "DB 오류", f"상세정보 조회 중 오류가 발생했습니다.\n{error}")

    def open_selected_product_steps(self, _item=None) -> None:
        """더블클릭한 제품 작업의 STEP 작업시간 모달을 엽니다."""
        row = self.product_table.currentRow()
        if row < 0 or self.product_table.item(row, 0) is None:
            return
        product_run = self.product_table.item(row, 0).data(Qt.UserRole)
        dialog = StepHistoryDialog(product_run, self.database_manager, self)
        dialog.step_selected.connect(self.load_step_pauses)
        initial_step_run_id = dialog.current_step_run_id()
        if initial_step_run_id is not None:
            self.load_step_pauses(initial_step_run_id)
        dialog.exec_()

    def load_pause_history(self) -> None:
        """직원의 전체 일시정지 이력을 불러옵니다."""
        try:
            self.selected_step_run_id = None
            pauses = self.database_manager.get_employee_pause_logs(self.employee_id)
            rows = []
            for item in pauses:
                resumed = item["resumed_at"] if item["resumed_at"] else "일시정지 중"
                duration = (
                    "진행 중" if item["pause_seconds"] is None
                    else f"{int(item['pause_seconds'])}초"
                )
                rows.append([
                    item["product_id"],
                    item["product_name"],
                    f"STEP {item['step_no']}",
                    item["paused_at"],
                    resumed,
                    duration,
                ])
            self._fill_table(self.pause_table, rows)
            for row_index, item in enumerate(pauses):
                if item["resumed_at"] is None:
                    for col in range(len(rows[row_index])):
                        cell = self.pause_table.item(row_index, col)
                        if cell:
                            cell.setForeground(QColor("#826532"))
        except Exception as error:
            QMessageBox.critical(
                self, "DB 오류", f"일시정지 조회 중 오류가 발생했습니다.\n{error}"
            )

    def clear_pause_history(self) -> None:
        """일시정지 이력을 직원의 전체 이력으로 복원합니다."""
        self.load_pause_history()

    def load_step_pauses(self, step_run_id: int) -> None:
        """STEP 모달에서 선택한 STEP의 일시정지 이력을 불러옵니다."""
        try:
            self.selected_step_run_id = int(step_run_id)
            pauses = self.database_manager.get_pause_logs(self.selected_step_run_id)
            rows = []
            for item in pauses:
                resumed = item["resumed_at"] if item["resumed_at"] else "일시정지 중"
                duration = (
                    "진행 중" if item["pause_seconds"] is None
                    else f"{int(item['pause_seconds'])}초"
                )
                rows.append([
                    item.get("product_id", "—"),
                    item.get("product_name", "—"),
                    f"STEP {item.get('step_no', '—')}",
                    item["paused_at"],
                    resumed,
                    duration,
                ])
            self._fill_table(self.pause_table, rows)
            for row_index, item in enumerate(pauses):
                if item["resumed_at"] is None:
                    for col in range(len(rows[row_index])):
                        cell = self.pause_table.item(row_index, col)
                        if cell:
                            cell.setForeground(QColor("#826532"))
        except Exception as error:
            QMessageBox.critical(
                self, "DB 오류", f"일시정지 조회 중 오류가 발생했습니다.\n{error}"
            )

    def send_employee_message(self) -> None:
        """작성 Dialog를 열고 선택 직원에게 TCP 메시지를 전송합니다."""
        dialog = EmployeeMessageDialog(
            self.employee_id, self.name_label.text(), self
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        result = self.tcp_client.send_employee_message(
            self.employee_id, dialog.message_text()
        )
        if result.success:
            QMessageBox.information(self, "메시지 전송 완료", result.message)
        else:
            QMessageBox.warning(
                self, "메시지 전송 실패",
                result.message + "\n\n관리자 프로그램은 계속 사용할 수 있습니다.",
            )
