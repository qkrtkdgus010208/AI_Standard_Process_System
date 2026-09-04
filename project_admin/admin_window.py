"""직원·제품·작업자 계정을 관리하는 관리자 메인 화면입니다."""

import sqlite3

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QButtonGroup, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from database_manager import DatabaseManager
from employee_detail_dialog import EmployeeDetailDialog
from product_dialog import ProductDialog
from product_detail_dialog import ProductDetailDialog
from tcp_client import TcpClient
from worker_account_dialog import (
    WorkerRegistrationDialog, WorkerRevocationConfirmDialog,
    WorkerRevocationDialog,
)


class AdminWindow(QMainWindow):
    """직원과 제품 업무 화면을 제공하는 관리자 프로그램입니다."""

    logout_requested = pyqtSignal()

    def __init__(self, database_manager: DatabaseManager,
                 tcp_client: TcpClient, admin_info: dict):
        super().__init__()
        self.database_manager = database_manager
        self.tcp_client = tcp_client
        self.admin_info = admin_info
        self._pending_employee_ids: set[str] = set()
        self._employee_row_by_id: dict[str, int] = {}
        self._employee_refresh_timer = QTimer(self)
        self._employee_refresh_timer.setSingleShot(True)
        self._employee_refresh_timer.setInterval(1000)
        self._employee_refresh_timer.timeout.connect(self._refresh_changed_employees)
        self.setWindowTitle("Team STEP · 관리자")
        self.setMinimumSize(1050, 700)
        self.resize(1220, 820)
        self._create_ui()
        self.switch_page(0)

    @staticmethod
    def _metric_card(label: str, value: str, accent: str = "#315E91"):
        """직원 현황을 표시하는 작은 지표 카드를 만듭니다."""
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(88)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 13, 18, 13)
        layout.setSpacing(3)
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        value_label.setStyleSheet(f"color:{accent};font-size:22px;font-weight:700;")
        label_widget = QLabel(label)
        label_widget.setObjectName("metricLabel")
        layout.addWidget(value_label)
        layout.addWidget(label_widget)
        return card, value_label

    @staticmethod
    def _page_heading(section: str, title: str, subtitle: str) -> QVBoxLayout:
        """각 관리 Page에 동일한 제목 영역을 만듭니다."""
        section_label = QLabel(section)
        section_label.setObjectName("eyebrow")
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("subtitle")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(section_label)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return layout

    @staticmethod
    def _prepare_table(table: QTableWidget) -> None:
        """관리 Page의 표를 동일한 읽기 전용 형태로 설정합니다."""
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(46)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)

    def _create_ui(self) -> None:
        """상단 Header, 2개 메뉴, Stacked Page를 구성합니다."""
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(70)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(28, 0, 28, 0)
        logo_mark = QLabel("S")
        logo_mark.setFixedSize(38, 38)
        logo_mark.setAlignment(Qt.AlignCenter)
        logo_mark.setStyleSheet(
            "color:#FFFFFF;background:#315E91;border-radius:8px;font-weight:900;"
        )
        logo_text = QLabel("Team STEP")
        logo_text.setStyleSheet("font-size:14px;font-weight:700;color:#263442;")
        admin_badge = QLabel(
            f"●  {self.admin_info['name']} · {self.admin_info['employee_id']}"
        )
        admin_badge.setStyleSheet(
            "color:#445362;background:#F6F8FA;border:1px solid #D7DFE7;"
            "border-radius:15px;padding:7px 12px;"
        )
        refresh_button = QPushButton("새로고침")
        refresh_button.setToolTip("현재 보고 있는 관리 화면의 데이터를 다시 조회합니다.")
        refresh_button.clicked.connect(self.refresh_current_page)
        logout_button = QPushButton("로그아웃")
        logout_button.setObjectName("dangerButton")
        logout_button.clicked.connect(self.logout_requested.emit)
        top_layout.addWidget(logo_mark)
        top_layout.addWidget(logo_text)
        top_layout.addStretch()
        top_layout.addWidget(admin_badge)
        top_layout.addSpacing(8)
        top_layout.addWidget(refresh_button)
        top_layout.addSpacing(6)
        top_layout.addWidget(logout_button)

        navigation = QFrame()
        navigation.setObjectName("navigationBar")
        navigation_layout = QHBoxLayout(navigation)
        navigation_layout.setContentsMargins(28, 10, 28, 10)
        navigation_layout.setSpacing(8)
        self.navigation_group = QButtonGroup(self)
        self.navigation_group.setExclusive(True)
        menu_names = ("직원 관리", "제품 관리")
        self.navigation_buttons = []
        for index, menu_name in enumerate(menu_names):
            button = QPushButton(menu_name)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked, page=index: self.switch_page(page))
            self.navigation_group.addButton(button, index)
            self.navigation_buttons.append(button)
            navigation_layout.addWidget(button)
        navigation_layout.addStretch()

        self.page_stack = QStackedWidget()
        self.page_stack.addWidget(self._build_employee_page())
        self.page_stack.addWidget(self._build_product_page())

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(top_bar)
        root_layout.addWidget(navigation)
        root_layout.addWidget(self.page_stack, 1)
        root = QWidget()
        root.setLayout(root_layout)
        self.setCentralWidget(root)

    def _build_employee_page(self) -> QWidget:
        """기존 직원 조회·상태·상세정보 Page를 만듭니다."""
        all_card, self.total_employee_value = self._metric_card("전체 등록 계정", "0")
        worker_card, self.worker_value = self._metric_card("생산 작업자", "0", "#3F6F96")
        admin_card, self.admin_value = self._metric_card("관리자 계정", "0", "#826532")
        working_card, self.working_worker_value = self._metric_card(
            "현재 출근 작업자", "0", "#2F7D4A"
        )
        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        for card in (all_card, worker_card, admin_card, working_card):
            metrics.addWidget(card)

        search_card = QFrame()
        search_card.setObjectName("card")
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(18, 14, 18, 14)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("직원번호 또는 이름 · 빈 칸은 전체 조회")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self.search_employees)
        search_button = QPushButton("검색")
        search_button.setObjectName("primaryButton")
        search_button.clicked.connect(self.search_employees)
        detail_button = QPushButton("선택 직원 상세")
        detail_button.clicked.connect(self.open_selected_employee)
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(search_button)
        search_layout.addWidget(detail_button)

        table_card = QFrame()
        table_card.setObjectName("card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 15, 18, 18)
        header_layout = QHBoxLayout()
        list_title = QLabel("직원 목록")
        list_title.setObjectName("sectionTitle")
        self.result_count_label = QLabel("0명")
        self.result_count_label.setObjectName("eyebrow")
        header_layout.addWidget(list_title)
        header_layout.addStretch()
        header_layout.addWidget(self.result_count_label)
        self.result_table = QTableWidget(0, 6)
        self.result_table.setHorizontalHeaderLabels(
            ["직원번호", "이름", "출근 여부", "진행 중인 제품", "현재 STEP", "권한"]
        )
        self._prepare_table(self.result_table)
        table_header = self.result_table.horizontalHeader()
        table_header.setSectionResizeMode(0, QHeaderView.Fixed)
        table_header.setSectionResizeMode(1, QHeaderView.Fixed)
        table_header.setSectionResizeMode(2, QHeaderView.Fixed)
        table_header.setSectionResizeMode(3, QHeaderView.Stretch)
        table_header.setSectionResizeMode(4, QHeaderView.Fixed)
        table_header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.result_table.setColumnWidth(0, 125)
        self.result_table.setColumnWidth(1, 150)
        self.result_table.setColumnWidth(2, 120)
        self.result_table.setColumnWidth(4, 125)
        self.result_table.setColumnWidth(5, 105)
        self.result_table.doubleClicked.connect(self.open_selected_employee)
        table_layout.addLayout(header_layout)
        table_layout.addWidget(self.result_table)

        layout = QVBoxLayout()
        layout.setContentsMargins(28, 18, 28, 26)
        layout.setSpacing(13)
        heading = QHBoxLayout()
        heading.addLayout(self._page_heading(
            "직원 관리", "직원 조회", "직원의 출근 상태, 진행 중인 공정 확인"
        ))
        heading.addStretch()
        register_account_button = QPushButton("계정 등록")
        register_account_button.setObjectName("primaryButton")
        register_account_button.clicked.connect(self.open_worker_registration)
        revoke_account_button = QPushButton("계정 말소")
        revoke_account_button.setObjectName("dangerButton")
        revoke_account_button.clicked.connect(self.open_worker_revocation)
        heading.addWidget(register_account_button, 0, Qt.AlignBottom)
        heading.addWidget(revoke_account_button, 0, Qt.AlignBottom)
        layout.addLayout(heading)
        layout.addLayout(metrics)
        layout.addWidget(search_card)
        layout.addWidget(table_card, 1)
        page = QWidget()
        page.setLayout(layout)
        return page

    def _build_product_page(self) -> QWidget:
        """제품 검색·등록·수정·삭제 Page를 만듭니다."""
        toolbar = QFrame()
        toolbar.setObjectName("card")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(18, 14, 18, 14)
        self.product_search_input = QLineEdit()
        self.product_search_input.setPlaceholderText("제품번호 또는 제품명 · 빈 칸은 전체 조회")
        self.product_search_input.setClearButtonEnabled(True)
        self.product_search_input.returnPressed.connect(self.search_products)
        product_search_button = QPushButton("검색")
        product_search_button.setObjectName("primaryButton")
        product_search_button.clicked.connect(self.search_products)
        edit_button = QPushButton("선택 제품 수정")
        edit_button.clicked.connect(self.edit_selected_product)
        detail_button = QPushButton("선택 제품 상세")
        detail_button.clicked.connect(self.open_selected_product)
        toolbar_layout.addWidget(self.product_search_input, 1)
        toolbar_layout.addWidget(product_search_button)
        toolbar_layout.addWidget(detail_button)
        toolbar_layout.addWidget(edit_button)

        table_card = QFrame()
        table_card.setObjectName("card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 15, 18, 18)
        table_header = QHBoxLayout()
        table_title = QLabel("제품 목록")
        table_title.setObjectName("sectionTitle")
        self.product_count_label = QLabel("0개")
        self.product_count_label.setObjectName("eyebrow")
        table_header.addWidget(table_title)
        table_header.addStretch()
        table_header.addWidget(self.product_count_label)
        self.product_table = QTableWidget(0, 6)
        self.product_table.setHorizontalHeaderLabels(
            ["제품번호", "제품명", "전체 STEP", "완료 수량", "불량 수량", "불량률"]
        )
        self._prepare_table(self.product_table)
        product_header = self.product_table.horizontalHeader()
        product_header.setSectionResizeMode(0, QHeaderView.Fixed)
        product_header.setSectionResizeMode(1, QHeaderView.Stretch)
        product_header.setSectionResizeMode(2, QHeaderView.Fixed)
        for column in range(3, 6):
            product_header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.product_table.setColumnWidth(0, 150)
        self.product_table.setColumnWidth(2, 110)
        self.product_table.setColumnWidth(3, 110)
        self.product_table.setColumnWidth(4, 110)
        self.product_table.setColumnWidth(5, 100)
        self.product_table.doubleClicked.connect(self.open_selected_product)
        table_layout.addLayout(table_header)
        table_layout.addWidget(self.product_table)

        layout = QVBoxLayout()
        layout.setContentsMargins(28, 18, 28, 26)
        layout.setSpacing(13)
        heading = QHBoxLayout()
        heading.addLayout(self._page_heading(
            "제품 관리", "제품 목록", "조립 제품, 제품별 전체 STEP 수 관리"
        ))
        heading.addStretch()
        add_button = QPushButton("제품 등록")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self.add_product)
        delete_button = QPushButton("제품 삭제")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_selected_product)
        heading.addWidget(add_button, 0, Qt.AlignBottom)
        heading.addWidget(delete_button, 0, Qt.AlignBottom)
        layout.addLayout(heading)
        layout.addWidget(toolbar)
        layout.addWidget(table_card, 1)
        page = QWidget()
        page.setLayout(layout)
        return page

    def switch_page(self, page_index: int) -> None:
        """선택한 관리 Page로 이동하고 최신 데이터를 조회합니다."""
        self.page_stack.setCurrentIndex(page_index)
        self.navigation_buttons[page_index].setChecked(True)
        if page_index == 0:
            self.search_employees()
        else:
            self.search_products()

    def refresh_current_page(self) -> None:
        """상단 공통 버튼에서 현재 선택된 관리 Page를 새로고침합니다."""
        if self.page_stack.currentIndex() == 0:
            self.search_employees()
        else:
            self.search_products()

    def search_employees(self) -> None:
        """검색어로 직원을 조회하고 상태 표와 지표를 갱신합니다."""
        try:
            employees = self.database_manager.search_employees(self.search_input.text())
            counts = self.database_manager.get_employee_counts()
        except Exception as error:
            QMessageBox.critical(self, "DB 오류", f"직원 검색 중 오류가 발생했습니다.\n{error}")
            return
        self.total_employee_value.setText(str(counts["total_count"]))
        self.worker_value.setText(str(counts["worker_count"]))
        self.admin_value.setText(str(counts["admin_count"]))
        self.working_worker_value.setText(str(counts["working_worker_count"]))
        self.result_table.setRowCount(len(employees))
        self._employee_row_by_id.clear()
        for row_index, employee in enumerate(employees):
            employee_id = str(employee.get("employee_id", ""))
            self._employee_row_by_id[employee_id] = row_index
            self._update_employee_row(row_index, employee)
        self.result_count_label.setText(f"{len(employees)}명")

    def _update_employee_row(self, row_index: int, employee: dict) -> None:
        """직원 한 명의 현재 상태 행만 다시 표시합니다."""
        attendance = employee.get("attendance_status", "off")
        role = employee.get("role", "")
        if role == "admin":
            is_current_admin = employee.get("employee_id") == self.admin_info["employee_id"]
            attendance_text = "●  접속 중" if is_current_admin else "—"
            attendance_color = "#2F7D4A" if is_current_admin else "#778391"
        else:
            attendance_text = "●  출근" if attendance == "working" else "●  미출근"
            attendance_color = "#2F7D4A" if attendance == "working" else "#B45656"
        current_step = employee.get("current_step")
        values = (
            employee.get("employee_id", ""), employee.get("name", ""),
            attendance_text, employee.get("active_product_name") or "—",
            f"STEP {current_step}" if current_step is not None else "—",
            {"admin": "관리자", "worker": "작업자"}.get(role, ""),
        )
        for column_index, display_value in enumerate(values):
            item = QTableWidgetItem(str(display_value))
            item.setToolTip(str(display_value))
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            if column_index == 2:
                item.setForeground(QColor(attendance_color))
            elif column_index == 4 and current_step is not None:
                item.setForeground(QColor("#315E91"))
            elif column_index == 5:
                item.setForeground(QColor("#826532" if role == "admin" else "#315E91"))
            self.result_table.setItem(row_index, column_index, item)

    @pyqtSlot(dict)
    def queue_employee_refresh(self, state: dict) -> None:
        """상태 신호의 직원번호를 모아 1초 뒤 한 번만 부분 갱신합니다."""
        employee_id = str(state.get("employee_id", "")).strip()
        if not employee_id:
            return
        self._pending_employee_ids.add(employee_id)
        if not self._employee_refresh_timer.isActive():
            self._employee_refresh_timer.start()

    def _refresh_changed_employees(self) -> None:
        """현재 직원 목록에 표시된 변경 직원 행만 한 번의 조회로 갱신합니다."""
        employee_ids = self._pending_employee_ids
        self._pending_employee_ids = set()
        if self.page_stack.currentIndex() != 0 or not employee_ids:
            return
        visible_ids = employee_ids.intersection(self._employee_row_by_id)
        try:
            if visible_ids:
                employees = self.database_manager.get_employee_monitoring_rows(visible_ids)
                for employee in employees:
                    row_index = self._employee_row_by_id.get(str(employee["employee_id"]))
                    if row_index is not None:
                        self._update_employee_row(row_index, employee)
            self.working_worker_value.setText(
                str(self.database_manager.get_working_worker_count())
            )
        except Exception:
            # 자동 갱신 실패는 다음 신호나 수동 새로고침에서 복구합니다.
            return

    def open_selected_employee(self, _index=None) -> None:
        """선택된 직원의 상세정보 Dialog를 엽니다."""
        row = self.result_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "직원 선택", "상세정보를 확인할 직원을 선택하세요.")
            return
        dialog = EmployeeDetailDialog(
            self.result_table.item(row, 0).text(), self.database_manager,
            self.tcp_client, self,
        )
        dialog.exec_()
        self.search_employees()

    def search_products(self) -> None:
        """검색어로 제품 목록을 갱신합니다."""
        try:
            products = self.database_manager.search_products(self.product_search_input.text())
        except Exception as error:
            QMessageBox.critical(self, "DB 오류", f"제품 검색 중 오류가 발생했습니다.\n{error}")
            return
        self.product_table.setRowCount(len(products))
        for row_index, product in enumerate(products):
            values = (
                product["product_id"], product["product_name"], product["total_steps"],
                product.get("completed_count", 0), product.get("defect_count", 0),
                f"{float(product.get('defect_rate', 0)):.1f}%",
            )
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                item.setTextAlignment(
                    Qt.AlignCenter if column_index != 1 else Qt.AlignVCenter | Qt.AlignLeft
                )
                if column_index in (4, 5) and product.get("defect_count", 0):
                    item.setForeground(QColor("#B45656"))
                self.product_table.setItem(row_index, column_index, item)
        self.product_count_label.setText(f"{len(products)}개")

    def add_product(self) -> None:
        """제품 등록 Dialog의 입력값을 DB에 저장합니다."""
        dialog = ProductDialog(parent=self)
        if dialog.exec_() != ProductDialog.Accepted:
            return
        data = dialog.get_product_data()
        try:
            self.database_manager.create_product(**data)
            self.search_products()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "등록 실패", "이미 사용 중인 제품번호입니다.")
        except Exception as error:
            QMessageBox.warning(self, "등록 실패", str(error))

    def open_selected_product(self, _index=None) -> None:
        """선택 제품의 STEP별 품질 상세 Dialog를 엽니다."""
        row = self.product_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "제품 선택", "상세정보를 확인할 제품을 선택하세요.")
            return
        product_id = self.product_table.item(row, 0).text()
        product = self.database_manager.get_product(product_id)
        if product is None:
            QMessageBox.warning(self, "조회 실패", "제품을 찾을 수 없습니다.")
            return
        ProductDetailDialog(product, self.database_manager, self).exec_()
        self.search_products()

    def edit_selected_product(self, _index=None) -> None:
        """선택한 제품의 제품명과 STEP 수를 수정합니다."""
        row = self.product_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "제품 선택", "수정할 제품을 선택하세요.")
            return
        product_id = self.product_table.item(row, 0).text()
        product = self.database_manager.get_product(product_id)
        if product is None:
            QMessageBox.warning(self, "조회 실패", "제품을 찾을 수 없습니다.")
            return
        dialog = ProductDialog(product, self)
        if dialog.exec_() != ProductDialog.Accepted:
            return
        data = dialog.get_product_data()
        try:
            self.database_manager.update_product(**data)
            self.search_products()
        except Exception as error:
            QMessageBox.warning(self, "수정 실패", str(error))

    def delete_selected_product(self) -> None:
        """선택한 제품을 확인 후 삭제합니다."""
        row = self.product_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "제품 선택", "삭제할 제품을 선택하세요.")
            return
        product_id = self.product_table.item(row, 0).text()
        product_name = self.product_table.item(row, 1).text()
        answer = QMessageBox.question(
            self, "제품 삭제", f"{product_name} ({product_id}) 제품을 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.database_manager.delete_product(product_id)
            self.search_products()
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "삭제 실패", "작업 이력이 있는 제품은 삭제할 수 없습니다.")
        except Exception as error:
            QMessageBox.warning(self, "삭제 실패", str(error))

    def open_worker_registration(self) -> None:
        """작업자 계정 등록 Dialog의 입력값을 저장합니다."""
        dialog = WorkerRegistrationDialog(self)
        if dialog.exec_() != WorkerRegistrationDialog.Accepted:
            return
        data = dialog.worker_data()
        try:
            self.database_manager.create_worker(**data)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "등록 실패", "이미 사용 중인 직원번호입니다.")
            return
        except Exception as error:
            QMessageBox.warning(self, "등록 실패", str(error))
            return
        QMessageBox.information(
            self, "등록 완료",
            f"작업자 {data['name']} ({data['employee_id']}) 계정을 등록했습니다.",
        )
        self.search_employees()

    def open_worker_revocation(self) -> None:
        """직원번호 입력과 최종 확인 후 작업자 계정을 말소합니다."""
        dialog = WorkerRevocationDialog(self)
        if dialog.exec_() != WorkerRevocationDialog.Accepted:
            return
        employee_id = dialog.employee_id()
        try:
            employee = self.database_manager.get_employee(employee_id)
            employee_status = next(
                (
                    item for item in self.database_manager.search_employees(employee_id)
                    if item.get("employee_id") == employee_id
                ),
                None,
            )
            work_sessions = self.database_manager.get_work_sessions(employee_id)
            product_runs = self.database_manager.get_product_runs(employee_id)
            defect_logs = self.database_manager.get_defect_logs(employee_id)
        except Exception as error:
            QMessageBox.warning(self, "조회 실패", str(error))
            return
        if employee is None:
            QMessageBox.warning(self, "말소 실패", "해당 직원번호의 계정을 찾을 수 없습니다.")
            return
        if employee.get("role") != "worker":
            QMessageBox.warning(self, "말소 실패", "작업자 계정만 말소할 수 있습니다.")
            return
        employee_status = employee_status or {}
        attendance = (
            "출근 중" if employee_status.get("attendance_status") == "working" else "미출근"
        )
        active_product = employee_status.get("active_product_name") or "없음"
        current_step = employee_status.get("current_step")
        step_text = f"STEP {current_step}" if current_step is not None else "없음"
        latest_login = work_sessions[0]["login_at"] if work_sessions else "기록 없음"
        confirm_dialog = WorkerRevocationConfirmDialog(
            {
                "employee_id": employee_id,
                "name": employee["name"],
                "attendance": attendance,
                "active_product": active_product,
                "current_step": step_text,
                "latest_login": latest_login,
                "product_run_count": len(product_runs),
                "defect_count": len(defect_logs),
            },
            self,
        )
        if confirm_dialog.exec_() != WorkerRevocationConfirmDialog.Accepted:
            return
        try:
            revoked = self.database_manager.revoke_worker(employee_id)
        except Exception as error:
            QMessageBox.warning(self, "말소 실패", str(error))
            return
        QMessageBox.information(
            self, "말소 완료",
            f"작업자 {revoked['name']} ({revoked['employee_id']}) 계정을 말소했습니다.",
        )
        self.search_employees()
