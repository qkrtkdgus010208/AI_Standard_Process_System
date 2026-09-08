"""Employee and attendance persistence operations."""

from __future__ import annotations

import os
from typing import Callable, Optional

from state_types import EmployeeIdentity

class EmployeeRepository:
    """직원 계정과 출근 현황을 조회·변경하는 저장소입니다."""

    def __init__(self, connect: Callable, verify_password: Callable, hash_password: Callable):
        self.connect = connect
        self.verify_password = verify_password
        self.hash_password = hash_password

    def verify_admin_login(
        self, employee_id: str, password: str
    ) -> Optional[EmployeeIdentity]:
        """관리자 역할의 계정과 비밀번호를 확인합니다."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT employee_id, name, password_hash, role FROM employees
                   WHERE employee_id = ? AND role = ?""", (employee_id.strip(), "admin")
            ).fetchone()
        if row and self.verify_password(password, row["password_hash"]):
            return {"employee_id": row["employee_id"], "name": row["name"], "role": row["role"]}
        return None

    def verify_worker_login(
        self, employee_id: str, password: str
    ) -> Optional[EmployeeIdentity]:
        """작업자 역할의 계정과 비밀번호를 확인합니다."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT employee_id, name, password_hash, role FROM employees
                   WHERE employee_id = ? AND role = ?""", (employee_id.strip(), "worker")
            ).fetchone()
        if row and self.verify_password(password, row["password_hash"]):
            return {"employee_id": row["employee_id"], "name": row["name"], "role": row["role"]}
        return None

    def search_employees(self, keyword: str = "") -> list[dict]:
        """직원 검색 결과와 출근·공정 진행 상태를 반환합니다."""
        search_text = f"%{keyword.strip()}%"
        with self.connect() as connection:
            rows = connection.execute(_EMPLOYEE_MONITORING_SELECT + """
                WHERE e.role IN ('admin', 'worker')
                  AND (e.employee_id LIKE ? OR e.name LIKE ?)
                ORDER BY e.employee_id""", (search_text, search_text)).fetchall()
        return [dict(row) for row in rows]

    def get_employee_monitoring_rows(self, employee_ids: set[str]) -> list[dict]:
        """변경된 직원의 모니터링 행을 한 번에 조회합니다."""
        cleaned_ids = sorted({str(item).strip() for item in employee_ids if str(item).strip()})
        if not cleaned_ids:
            return []
        placeholders = ",".join("?" for _item in cleaned_ids)
        with self.connect() as connection:
            rows = connection.execute(_EMPLOYEE_MONITORING_SELECT + f"""
                WHERE e.role IN ('admin', 'worker')
                  AND e.employee_id IN ({placeholders})
                ORDER BY e.employee_id""", cleaned_ids).fetchall()
        return [dict(row) for row in rows]

    def get_working_worker_count(self) -> int:
        """현재 열린 출근 기록이 있는 작업자 수를 조회합니다."""
        with self.connect() as connection:
            row = connection.execute("""SELECT COUNT(*) FROM employees AS e
                   WHERE e.role = 'worker' AND EXISTS (SELECT 1 FROM work_sessions AS ws
                   WHERE ws.employee_id = e.employee_id AND ws.login_at IS NOT NULL
                   AND ws.logout_at IS NULL)""").fetchone()
        return int(row[0])

    def get_employee_counts(self) -> dict:
        """관리자·작업자 계정 수와 현재 출근 작업자 수를 집계합니다."""
        with self.connect() as connection:
            row = connection.execute("""SELECT COUNT(*) AS total_count,
                       SUM(CASE WHEN e.role = 'worker' THEN 1 ELSE 0 END) AS worker_count,
                       SUM(CASE WHEN e.role = 'admin' THEN 1 ELSE 0 END) AS admin_count,
                       SUM(CASE WHEN e.role = 'worker' AND EXISTS (
                           SELECT 1 FROM work_sessions AS ws WHERE ws.employee_id = e.employee_id
                           AND ws.login_at IS NOT NULL AND ws.logout_at IS NULL)
                           THEN 1 ELSE 0 END) AS working_worker_count
                   FROM employees AS e WHERE e.role IN ('admin', 'worker')""").fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}

    def get_employee(self, employee_id: str) -> Optional[dict]:
        """직원 기본 정보를 조회합니다."""
        with self.connect() as connection:
            row = connection.execute("""SELECT employee_id, name, COALESCE(role, '') AS role
                   FROM employees WHERE employee_id = ?""", (employee_id,)).fetchone()
        return dict(row) if row else None

    def create_worker(self, employee_id: str, name: str, password: str) -> None:
        """작업자 역할로 새 계정을 생성합니다."""
        cleaned_id, cleaned_name = employee_id.strip(), name.strip()
        if not cleaned_id or not cleaned_name:
            raise ValueError("직원번호와 이름은 비어 있을 수 없습니다.")
        with self.connect() as connection:
            connection.execute("""INSERT INTO employees(employee_id, name, password_hash, role)
                   VALUES (?, ?, ?, ?)""", (cleaned_id, cleaned_name, self.hash_password(password), "worker"))

    def revoke_worker(self, employee_id: str) -> dict:
        """이력을 보존하면서 작업자 계정과 열린 출근을 종료합니다."""
        cleaned_id = employee_id.strip()
        if not cleaned_id:
            raise ValueError("직원번호는 비어 있을 수 없습니다.")
        replacement_hash = self.hash_password(os.urandom(32).hex())
        with self.connect() as connection:
            employee = connection.execute("SELECT employee_id, name, role FROM employees WHERE employee_id = ?", (cleaned_id,)).fetchone()
            if employee is None:
                raise ValueError("해당 직원번호의 계정을 찾을 수 없습니다.")
            if employee["role"] != "worker":
                raise ValueError("작업자 계정만 말소할 수 있습니다.")
            connection.execute("""UPDATE work_sessions SET logout_at = datetime('now', '+9 hours')
                   WHERE employee_id = ? AND logout_at IS NULL""", (cleaned_id,))
            connection.execute("""UPDATE employees SET role = 'revoked', password_hash = ?
                   WHERE employee_id = ?""", (replacement_hash, cleaned_id))
        return {"employee_id": employee["employee_id"], "name": employee["name"]}


_EMPLOYEE_MONITORING_SELECT = """
    SELECT e.employee_id, e.name, COALESCE(e.role, '') AS role,
        CASE WHEN EXISTS (SELECT 1 FROM work_sessions AS ws WHERE ws.employee_id = e.employee_id
          AND ws.login_at IS NOT NULL AND ws.logout_at IS NULL) THEN 'working' ELSE 'off' END AS attendance_status,
        COALESCE((SELECT COALESCE(p.product_name, pr.product_id) FROM product_runs AS pr
          LEFT JOIN products AS p ON p.product_id = pr.product_id WHERE pr.employee_id = e.employee_id
          AND pr.completed_at IS NULL ORDER BY pr.started_at DESC, pr.product_run_id DESC LIMIT 1), '') AS active_product_name,
        (SELECT sr.step_no FROM step_runs AS sr WHERE sr.product_run_id = (SELECT pr2.product_run_id
          FROM product_runs AS pr2 WHERE pr2.employee_id = e.employee_id AND pr2.completed_at IS NULL
          ORDER BY pr2.started_at DESC, pr2.product_run_id DESC LIMIT 1) AND sr.completed_at IS NULL
          ORDER BY sr.started_at DESC, sr.step_run_id DESC LIMIT 1) AS current_step
    FROM employees AS e
"""
