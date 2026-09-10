"""Work session and production-history queries."""

from __future__ import annotations

from typing import Callable, Optional


class WorkHistoryRepository:
    """근무·제품·STEP·불량·일시정지 이력 저장소입니다."""

    def __init__(self, connect: Callable, standard_work_seconds: int):
        self.connect = connect
        self.standard_work_seconds = standard_work_seconds

    def start_work_session(self, employee_id: str) -> int:
        """열린 출근 기록이 없을 때만 출근 기록을 생성합니다."""
        with self.connect() as connection:
            existing = connection.execute("""SELECT session_id FROM work_sessions
                WHERE employee_id = ? AND logout_at IS NULL ORDER BY login_at DESC, session_id DESC LIMIT 1""", (employee_id,)).fetchone()
            if existing:
                return int(existing["session_id"])
            cursor = connection.execute("INSERT INTO work_sessions(employee_id, login_at, logout_at) VALUES (?, datetime('now', '+9 hours'), NULL)", (employee_id,))
            return int(cursor.lastrowid)

    def end_work_session(self, employee_id: str) -> None:
        """직원의 열린 출근 기록을 종료합니다."""
        with self.connect() as connection:
            connection.execute("UPDATE work_sessions SET logout_at = datetime('now', '+9 hours') WHERE employee_id = ? AND logout_at IS NULL", (employee_id,))

    def get_incomplete_work_state(self, employee_id: str) -> Optional[dict]:
        """직원이 이어서 진행할 미완료 공정 상태를 조회합니다."""
        with self.connect() as connection:
            product_run = connection.execute("""SELECT pr.product_run_id, pr.product_id, p.product_name, p.total_steps
                FROM product_runs AS pr JOIN products AS p ON p.product_id = pr.product_id
                WHERE pr.employee_id = ? AND pr.completed_at IS NULL ORDER BY pr.started_at DESC, pr.product_run_id DESC LIMIT 1""", (employee_id,)).fetchone()
            if product_run is None:
                return None
            step_run = connection.execute("SELECT step_run_id, step_no FROM step_runs WHERE product_run_id = ? ORDER BY step_no DESC, step_run_id DESC LIMIT 1", (product_run["product_run_id"],)).fetchone()
            current_step = int(step_run["step_no"]) if step_run else 1
            state, last_result = "running", "waiting"
            if step_run is not None:
                if connection.execute("SELECT 1 FROM pause_logs WHERE step_run_id = ? AND resumed_at IS NULL LIMIT 1", (step_run["step_run_id"],)).fetchone() is not None:
                    state = "paused"
                latest_judgement = connection.execute("""SELECT jl.result FROM judgement_logs AS jl JOIN step_runs AS sr ON sr.step_run_id = jl.step_run_id
                    WHERE sr.product_run_id = ? ORDER BY jl.judgement_id DESC LIMIT 1""", (product_run["product_run_id"],)).fetchone()
                if latest_judgement is not None:
                    last_result = str(latest_judgement["result"])
        return {"product_id": str(product_run["product_id"]), "product_name": str(product_run["product_name"]), "total_steps": int(product_run["total_steps"]), "current_step": current_step, "state": state, "last_result": last_result}

    def get_work_sessions(self, employee_id: str) -> list[dict]:
        """출퇴근 시각과 경과 근무시간을 조회합니다."""
        with self.connect() as connection:
            rows = connection.execute("""SELECT session_id, login_at, logout_at,
                CASE WHEN login_at IS NULL THEN NULL ELSE MAX(0, CAST(ROUND((julianday(COALESCE(logout_at, datetime('now', '+9 hours'))) - julianday(login_at)) * 86400) AS INTEGER)) END AS worked_seconds,
                CASE WHEN logout_at IS NULL THEN 'working' WHEN login_at IS NOT NULL AND ROUND((julianday(logout_at) - julianday(login_at)) * 86400) >= ? THEN 'normal' ELSE 'short' END AS work_status
                FROM work_sessions WHERE employee_id = ? ORDER BY login_at DESC, session_id DESC""", (self.standard_work_seconds, employee_id)).fetchall()
        return [dict(row) for row in rows]

    def get_product_runs(self, employee_id: str) -> list[dict]:
        """직원의 제품 작업 회차와 검사 FAIL 횟수를 조회합니다."""
        with self.connect() as connection:
            rows = connection.execute("""SELECT pr.product_run_id, pr.product_id, COALESCE(p.product_name, pr.product_id) AS product_name,
                (SELECT COUNT(*) FROM judgement_logs AS jl JOIN step_runs AS jsr ON jsr.step_run_id = jl.step_run_id WHERE jsr.product_run_id = pr.product_run_id AND jl.result = 'fail') AS fail_count,
                pr.started_at, pr.completed_at, pr.result FROM product_runs AS pr LEFT JOIN products AS p ON p.product_id = pr.product_id
                WHERE pr.employee_id = ? ORDER BY pr.started_at DESC, pr.product_run_id DESC""", (employee_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_defect_logs(self, employee_id: str) -> list[dict]:
        """직원이 등록한 불량 이력을 최신순으로 조회합니다."""
        with self.connect() as connection:
            rows = connection.execute("""SELECT dl.defect_id, pr.product_run_id, pr.product_id, COALESCE(p.product_name, pr.product_id) AS product_name,
                sr.step_no, dl.defect_type, dl.detail, dl.defect_at FROM defect_logs AS dl JOIN step_runs AS sr ON sr.step_run_id = dl.step_run_id
                JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id LEFT JOIN products AS p ON p.product_id = pr.product_id
                WHERE pr.employee_id = ? ORDER BY dl.defect_at DESC, dl.defect_id DESC""", (employee_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_step_runs(self, product_run_id: int) -> list[dict]:
        """작업 회차의 STEP 작업시간과 PASS/FAIL을 조회합니다."""
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT
                    sr.step_run_id, sr.step_no, sr.started_at, sr.completed_at,
                    CASE
                        WHEN sr.started_at IS NULL OR sr.completed_at IS NULL THEN NULL
                        ELSE MAX(0, CAST(ROUND(
                            (julianday(sr.completed_at) - julianday(sr.started_at)) * 86400
                            - COALESCE(SUM(
                                CASE WHEN pl.paused_at IS NOT NULL AND pl.resumed_at IS NOT NULL
                                     THEN (julianday(pl.resumed_at) - julianday(pl.paused_at)) * 86400
                                     ELSE 0 END
                              ), 0)
                        ) AS INTEGER))
                    END AS actual_seconds,
                    COUNT(CASE WHEN jl.result = 'pass' THEN 1 END) AS pass_count,
                    COUNT(CASE WHEN jl.result = 'fail' THEN 1 END) AS fail_count,
                    CASE
                        WHEN COUNT(jl.judgement_id) = 0 THEN 0.0
                        ELSE ROUND(
                            100.0 * COUNT(CASE WHEN jl.result = 'fail' THEN 1 END)
                            / COUNT(jl.judgement_id), 1
                        )
                    END AS fail_rate
                FROM step_runs AS sr
                LEFT JOIN pause_logs AS pl ON pl.step_run_id = sr.step_run_id
                LEFT JOIN judgement_logs AS jl ON jl.step_run_id = sr.step_run_id
                WHERE sr.product_run_id = ?
                GROUP BY sr.step_run_id, sr.step_no, sr.started_at, sr.completed_at
                ORDER BY sr.step_no, sr.step_run_id
            """, (product_run_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_pause_logs(self, step_run_id: int) -> list[dict]:
        """특정 STEP의 일시정지 이력을 조회합니다."""
        with self.connect() as connection:
            rows = connection.execute("""SELECT pl.pause_id, pr.product_run_id, pr.product_id, COALESCE(p.product_name, pr.product_id) AS product_name,
                sr.step_run_id, sr.step_no, pl.paused_at, pl.resumed_at,
                CASE WHEN pl.paused_at IS NULL OR pl.resumed_at IS NULL THEN NULL ELSE MAX(0, CAST(ROUND((julianday(pl.resumed_at) - julianday(pl.paused_at)) * 86400) AS INTEGER)) END AS pause_seconds
                FROM pause_logs AS pl JOIN step_runs AS sr ON sr.step_run_id = pl.step_run_id JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id
                LEFT JOIN products AS p ON p.product_id = pr.product_id WHERE pl.step_run_id = ? ORDER BY pl.paused_at DESC, pl.pause_id DESC""", (step_run_id,)).fetchall()
        return [dict(row) for row in rows]

    def get_employee_pause_logs(self, employee_id: str) -> list[dict]:
        """직원의 전체 일시정지 이력을 조회합니다."""
        with self.connect() as connection:
            rows = connection.execute("""SELECT pl.pause_id, pr.product_run_id, pr.product_id, COALESCE(p.product_name, pr.product_id) AS product_name,
                sr.step_run_id, sr.step_no, pl.paused_at, pl.resumed_at,
                CASE WHEN pl.paused_at IS NULL OR pl.resumed_at IS NULL THEN NULL ELSE MAX(0, CAST(ROUND((julianday(pl.resumed_at) - julianday(pl.paused_at)) * 86400) AS INTEGER)) END AS pause_seconds
                FROM pause_logs AS pl JOIN step_runs AS sr ON sr.step_run_id = pl.step_run_id JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id
                LEFT JOIN products AS p ON p.product_id = pr.product_id WHERE pr.employee_id = ? ORDER BY pl.paused_at DESC, pl.pause_id DESC""", (employee_id,)).fetchall()
        return [dict(row) for row in rows]
