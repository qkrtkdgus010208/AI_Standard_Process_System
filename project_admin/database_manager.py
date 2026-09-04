"""Monitoring PC의 SQLite 데이터 접근을 담당하는 모듈입니다."""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import config

DEFAULT_DB_PATH = config.DATABASE_PATH
PASSWORD_ITERATIONS = 260_000
STANDARD_WORK_SECONDS = 9 * 60 * 60

EMPLOYEE_MONITORING_SELECT = """
    SELECT
        e.employee_id,
        e.name,
        COALESCE(e.role, '') AS role,
        CASE WHEN EXISTS (
            SELECT 1 FROM work_sessions AS ws
            WHERE ws.employee_id = e.employee_id
              AND ws.login_at IS NOT NULL
              AND ws.logout_at IS NULL
        ) THEN 'working' ELSE 'off' END AS attendance_status,
        COALESCE((
            SELECT COALESCE(p.product_name, pr.product_id)
            FROM product_runs AS pr
            LEFT JOIN products AS p ON p.product_id = pr.product_id
            WHERE pr.employee_id = e.employee_id
              AND pr.completed_at IS NULL
            ORDER BY pr.started_at DESC, pr.product_run_id DESC
            LIMIT 1
        ), '') AS active_product_name,
        (
            SELECT sr.step_no FROM step_runs AS sr
            WHERE sr.product_run_id = (
                SELECT pr2.product_run_id FROM product_runs AS pr2
                WHERE pr2.employee_id = e.employee_id
                  AND pr2.completed_at IS NULL
                ORDER BY pr2.started_at DESC, pr2.product_run_id DESC
                LIMIT 1
            )
              AND sr.completed_at IS NULL
            ORDER BY sr.started_at DESC, sr.step_run_id DESC
            LIMIT 1
        ) AS current_step
    FROM employees AS e
"""


class DatabaseManager:
    """UI와 분리하여 DB 연결, 조회, 비밀번호 검증을 담당합니다."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = str(Path(db_path).resolve())

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Foreign Key가 활성화된 연결을 만들고 안전하게 닫습니다."""
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA synchronous = NORMAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize_database(self) -> None:
        """DB 파일과 필요한 테이블을 없으면 생성합니다."""
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS employees (
                    employee_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT
                );
                CREATE TABLE IF NOT EXISTS products (
                    product_id TEXT PRIMARY KEY,
                    product_name TEXT NOT NULL,
                    total_steps INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS work_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id TEXT,
                    login_at DATETIME,
                    logout_at DATETIME,
                    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
                );
                CREATE TABLE IF NOT EXISTS product_runs (
                    product_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id TEXT,
                    product_id TEXT,
                    started_at DATETIME,
                    completed_at DATETIME,
                    result TEXT NOT NULL DEFAULT 'in_progress',
                    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
                    FOREIGN KEY (product_id) REFERENCES products(product_id)
                );
                CREATE TABLE IF NOT EXISTS step_runs (
                    step_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_run_id INTEGER,
                    step_no INTEGER,
                    started_at DATETIME,
                    completed_at DATETIME,
                    FOREIGN KEY (product_run_id) REFERENCES product_runs(product_run_id)
                );
                CREATE TABLE IF NOT EXISTS pause_logs (
                    pause_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    step_run_id INTEGER,
                    paused_at DATETIME,
                    resumed_at DATETIME,
                    FOREIGN KEY (step_run_id) REFERENCES step_runs(step_run_id)
                );
                CREATE TABLE IF NOT EXISTS defect_logs (
                    defect_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    step_run_id INTEGER NOT NULL UNIQUE,
                    defect_type TEXT NOT NULL DEFAULT 'manual',
                    detail TEXT NOT NULL DEFAULT '',
                    defect_at DATETIME NOT NULL DEFAULT (datetime('now', '+9 hours')),
                    FOREIGN KEY (step_run_id) REFERENCES step_runs(step_run_id)
                );
                CREATE TABLE IF NOT EXISTS judgement_logs (
                    judgement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    step_run_id INTEGER NOT NULL,
                    result TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'inspection',
                    detail TEXT NOT NULL DEFAULT '',
                    judged_at DATETIME NOT NULL DEFAULT (datetime('now', '+9 hours')),
                    FOREIGN KEY (step_run_id) REFERENCES step_runs(step_run_id)
                );
                CREATE TABLE IF NOT EXISTS product_quality_baselines (
                    product_id TEXT PRIMARY KEY,
                    reset_at DATETIME NOT NULL,
                    product_run_id_cutoff INTEGER NOT NULL DEFAULT 0,
                    judgement_id_cutoff INTEGER NOT NULL DEFAULT 0,
                    defect_id_cutoff INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (product_id) REFERENCES products(product_id)
                );
                CREATE TABLE IF NOT EXISTS worker_state_events (
                    state_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    state TEXT NOT NULL,
                    current_step INTEGER NOT NULL,
                    total_steps INTEGER NOT NULL,
                    last_result TEXT NOT NULL,
                    event TEXT NOT NULL DEFAULT '',
                    defect_type TEXT NOT NULL DEFAULT '',
                    detail TEXT NOT NULL DEFAULT '',
                    received_at DATETIME NOT NULL DEFAULT (datetime('now', '+9 hours')),
                    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
                    FOREIGN KEY (product_id) REFERENCES products(product_id)
                );
                CREATE INDEX IF NOT EXISTS idx_work_sessions_employee
                    ON work_sessions(employee_id);
                CREATE INDEX IF NOT EXISTS idx_product_runs_employee
                    ON product_runs(employee_id);
                CREATE INDEX IF NOT EXISTS idx_product_runs_product
                    ON product_runs(product_id, product_run_id);
                CREATE INDEX IF NOT EXISTS idx_step_runs_product_run
                    ON step_runs(product_run_id);
                CREATE INDEX IF NOT EXISTS idx_pause_logs_step_run
                    ON pause_logs(step_run_id);
                CREATE INDEX IF NOT EXISTS idx_worker_state_events_employee_time
                    ON worker_state_events(employee_id, received_at);
                CREATE INDEX IF NOT EXISTS idx_worker_state_events_product_time
                    ON worker_state_events(product_id, received_at);
                CREATE TABLE IF NOT EXISTS app_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            # 기존 factory.db에도 결과 컬럼을 안전하게 추가합니다.
            product_run_columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(product_runs)"
                ).fetchall()
            }
            if "result" not in product_run_columns:
                connection.execute(
                    "ALTER TABLE product_runs "
                    "ADD COLUMN result TEXT NOT NULL DEFAULT 'in_progress'"
                )
            self._migrate_normalized_quality_logs(connection)
            worker_event_columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(worker_state_events)"
                ).fetchall()
            }
            for column_name in ("event", "defect_type", "detail"):
                if column_name not in worker_event_columns:
                    connection.execute(
                        f"ALTER TABLE worker_state_events "
                        f"ADD COLUMN {column_name} TEXT NOT NULL DEFAULT ''"
                    )
            defect_log_columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(defect_logs)"
                ).fetchall()
            }
            for column_name, default_value in (("defect_type", "manual"), ("detail", "")):
                if column_name not in defect_log_columns:
                    connection.execute(
                        f"ALTER TABLE defect_logs "
                        f"ADD COLUMN {column_name} TEXT NOT NULL DEFAULT '{default_value}'"
                    )
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                DROP INDEX IF EXISTS idx_work_sessions_employee;
                DROP INDEX IF EXISTS idx_product_runs_employee;
                DROP INDEX IF EXISTS idx_step_runs_product_run;
                CREATE INDEX IF NOT EXISTS idx_work_sessions_employee_open
                    ON work_sessions(employee_id, logout_at);
                CREATE INDEX IF NOT EXISTS idx_product_runs_employee_open
                    ON product_runs(employee_id, completed_at, started_at, product_run_id);
                CREATE INDEX IF NOT EXISTS idx_step_runs_product_run_open
                    ON step_runs(product_run_id, completed_at, started_at, step_run_id);
                DROP INDEX IF EXISTS idx_defect_logs_step_time;
                CREATE INDEX IF NOT EXISTS idx_judgement_logs_step_time
                    ON judgement_logs(step_run_id, judged_at);
                """
            )
            connection.execute(
                """UPDATE product_runs SET result = 'pass'
                   WHERE completed_at IS NOT NULL AND result = 'in_progress'"""
            )
            self._migrate_legacy_utc_timestamps(connection)

    @staticmethod
    def _migrate_normalized_quality_logs(connection: sqlite3.Connection) -> None:
        """품질 로그의 유도 가능한 중복 키를 제거하고 기존 이력을 보존합니다."""
        judgement_columns = {
            row["name"] for row in connection.execute(
                "PRAGMA table_info(judgement_logs)"
            ).fetchall()
        }
        if "product_run_id" in judgement_columns:
            connection.executescript(
                """
                ALTER TABLE judgement_logs RENAME TO judgement_logs_legacy;
                CREATE TABLE judgement_logs (
                    judgement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    step_run_id INTEGER NOT NULL,
                    result TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'inspection',
                    detail TEXT NOT NULL DEFAULT '',
                    judged_at DATETIME NOT NULL DEFAULT (datetime('now', '+9 hours')),
                    FOREIGN KEY (step_run_id) REFERENCES step_runs(step_run_id)
                );
                INSERT INTO judgement_logs(
                    judgement_id, step_run_id, result, source, detail, judged_at
                )
                SELECT judgement_id, step_run_id, result, source, detail, judged_at
                FROM judgement_logs_legacy;
                DROP TABLE judgement_logs_legacy;
                """
            )

        defect_columns = {
            row["name"] for row in connection.execute(
                "PRAGMA table_info(defect_logs)"
            ).fetchall()
        }
        if "step_run_id" not in defect_columns:
            missing_step = connection.execute(
                """SELECT COUNT(*)
                   FROM defect_logs AS dl
                   WHERE NOT EXISTS (
                       SELECT 1 FROM step_runs AS sr
                       WHERE sr.product_run_id = dl.product_run_id
                         AND sr.step_no = dl.step_no
                   )"""
            ).fetchone()[0]
            if missing_step:
                raise RuntimeError(
                    "불량 이력에 대응하는 STEP 작업이 없어 DB 구조를 변환할 수 없습니다."
                )
            connection.executescript(
                """
                ALTER TABLE defect_logs RENAME TO defect_logs_legacy;
                CREATE TABLE defect_logs (
                    defect_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    step_run_id INTEGER NOT NULL UNIQUE,
                    defect_type TEXT NOT NULL DEFAULT 'manual',
                    detail TEXT NOT NULL DEFAULT '',
                    defect_at DATETIME NOT NULL DEFAULT (datetime('now', '+9 hours')),
                    FOREIGN KEY (step_run_id) REFERENCES step_runs(step_run_id)
                );
                INSERT INTO defect_logs(
                    defect_id, step_run_id, defect_type, detail, defect_at
                )
                SELECT dl.defect_id,
                       (SELECT sr.step_run_id
                        FROM step_runs AS sr
                        WHERE sr.product_run_id = dl.product_run_id
                          AND sr.step_no = dl.step_no
                        ORDER BY sr.step_run_id DESC LIMIT 1),
                       dl.defect_type, dl.detail, dl.defect_at
                FROM defect_logs_legacy AS dl;
                DROP TABLE defect_logs_legacy;
                """
            )

    @staticmethod
    def _migrate_legacy_utc_timestamps(connection: sqlite3.Connection) -> None:
        """기존 UTC 수신 기록을 한 번만 한국 표준시(UTC+9)로 보정합니다."""
        migration_key = "timestamps_kst_v1"
        if connection.execute(
            "SELECT 1 FROM app_metadata WHERE key = ?", (migration_key,)
        ).fetchone():
            return

        first_event_date = connection.execute(
            "SELECT date(MIN(received_at)) FROM worker_state_events"
        ).fetchone()[0]
        if first_event_date:
            for table_name, column_names in (
                ("work_sessions", ("login_at", "logout_at")),
                ("product_runs", ("started_at", "completed_at")),
                ("step_runs", ("started_at", "completed_at")),
                ("pause_logs", ("paused_at", "resumed_at")),
                ("judgement_logs", ("judged_at",)),
            ):
                for column_name in column_names:
                    connection.execute(
                        f"""UPDATE {table_name}
                            SET {column_name} = datetime({column_name}, '+9 hours')
                            WHERE {column_name} IS NOT NULL
                              AND date({column_name}) >= ?""",
                        (first_event_date,),
                    )
            connection.execute(
                """UPDATE worker_state_events
                   SET received_at = datetime(received_at, '+9 hours')"""
            )
            connection.execute(
                """UPDATE defect_logs
                   SET defect_at = datetime(defect_at, '+9 hours')"""
            )
        connection.execute(
            "INSERT INTO app_metadata(key, value) VALUES (?, 'complete')",
            (migration_key,),
        )

    @staticmethod
    def hash_password(password: str) -> str:
        """비밀번호를 PBKDF2-SHA256 형식으로 안전하게 해시합니다."""
        if not password:
            raise ValueError("비밀번호는 비어 있을 수 없습니다.")
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
        )
        return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"

    @staticmethod
    def verify_password(password: str, stored_hash: str) -> bool:
        """입력 비밀번호와 저장된 해시를 상수 시간 비교합니다."""
        try:
            algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            calculated = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
            )
            return hmac.compare_digest(calculated.hex(), digest_hex)
        except (AttributeError, TypeError, ValueError):
            return False

    def verify_admin_login(self, employee_id: str, password: str) -> Optional[dict]:
        """role이 admin인 계정만 확인하고 성공 시 관리자 정보를 반환합니다."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT employee_id, name, password_hash, role FROM employees
                   WHERE employee_id = ? AND role = ?""",
                (employee_id.strip(), "admin"),
            ).fetchone()
        if row and self.verify_password(password, row["password_hash"]):
            return {"employee_id": row["employee_id"], "name": row["name"], "role": row["role"]}
        return None

    def verify_worker_login(self, employee_id: str, password: str) -> Optional[dict]:
        """role이 worker인 작업자 계정을 해시 비밀번호로 확인합니다."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT employee_id, name, password_hash, role FROM employees
                   WHERE employee_id = ? AND role = ?""",
                (employee_id.strip(), "worker"),
            ).fetchone()
        if row and self.verify_password(password, row["password_hash"]):
            return {
                "employee_id": row["employee_id"],
                "name": row["name"],
                "role": row["role"],
            }
        return None

    def start_work_session(self, employee_id: str) -> int:
        """작업자 로그인 시 열린 출근 기록을 중복 없이 생성합니다."""
        with self.connect() as connection:
            existing = connection.execute(
                """SELECT session_id FROM work_sessions
                   WHERE employee_id = ? AND logout_at IS NULL
                   ORDER BY login_at DESC, session_id DESC LIMIT 1""",
                (employee_id,),
            ).fetchone()
            if existing:
                return int(existing["session_id"])
            cursor = connection.execute(
                """INSERT INTO work_sessions(employee_id, login_at, logout_at)
                   VALUES (?, datetime('now', '+9 hours'), NULL)""",
                (employee_id,),
            )
            return int(cursor.lastrowid)

    def end_work_session(self, employee_id: str) -> None:
        """작업자 로그아웃 시 해당 직원의 열린 출근 기록을 종료합니다."""
        with self.connect() as connection:
            connection.execute(
                """UPDATE work_sessions SET logout_at = datetime('now', '+9 hours')
                   WHERE employee_id = ? AND logout_at IS NULL""",
                (employee_id,),
            )

    def get_incomplete_work_state(self, employee_id: str) -> Optional[dict]:
        """로그인 작업자가 이어서 진행할 미완료 공정 상태를 조회합니다."""
        with self.connect() as connection:
            product_run = connection.execute(
                """SELECT pr.product_run_id, pr.product_id, p.product_name,
                          p.total_steps
                   FROM product_runs AS pr
                   JOIN products AS p ON p.product_id = pr.product_id
                   WHERE pr.employee_id = ? AND pr.completed_at IS NULL
                   ORDER BY pr.started_at DESC, pr.product_run_id DESC
                   LIMIT 1""",
                (employee_id,),
            ).fetchone()
            if product_run is None:
                return None

            step_run = connection.execute(
                """SELECT step_run_id, step_no
                   FROM step_runs
                   WHERE product_run_id = ?
                   ORDER BY step_no DESC, step_run_id DESC
                   LIMIT 1""",
                (product_run["product_run_id"],),
            ).fetchone()
            current_step = int(step_run["step_no"]) if step_run else 1
            state = "running"
            last_result = "waiting"
            if step_run is not None:
                open_pause = connection.execute(
                    """SELECT 1 FROM pause_logs
                       WHERE step_run_id = ? AND resumed_at IS NULL LIMIT 1""",
                    (step_run["step_run_id"],),
                ).fetchone()
                if open_pause is not None:
                    state = "paused"
                latest_judgement = connection.execute(
                    """SELECT jl.result
                       FROM judgement_logs AS jl
                       JOIN step_runs AS sr ON sr.step_run_id = jl.step_run_id
                       WHERE sr.product_run_id = ?
                       ORDER BY jl.judgement_id DESC LIMIT 1""",
                    (product_run["product_run_id"],),
                ).fetchone()
                if latest_judgement is not None:
                    last_result = str(latest_judgement["result"])

        return {
            "product_id": str(product_run["product_id"]),
            "product_name": str(product_run["product_name"]),
            "total_steps": int(product_run["total_steps"]),
            "current_step": current_step,
            "state": state,
            "last_result": last_result,
        }

    def record_worker_state(self, state_data: dict) -> Optional[int]:
        """수신 상태를 보존하고 공정·STEP·Pause 이력에 원자적으로 반영합니다."""
        employee_id = str(state_data.get("employee_id", "")).strip()
        product_id = str(state_data.get("product_id", "")).strip()
        product_name = str(state_data.get("product_name", "")).strip()
        state = str(state_data.get("state", "")).strip().lower()
        last_result = str(state_data.get("last_result", "waiting")).strip().lower()
        event_name = str(state_data.get("event", "")).strip().lower()
        defect_type = str(state_data.get("defect_type", "")).strip().lower()
        detail = str(state_data.get("detail", "")).strip()
        try:
            current_step = int(state_data.get("current_step", 0))
            total_steps = int(state_data.get("total_steps", 0))
        except (TypeError, ValueError) as error:
            raise ValueError("current_step과 total_steps는 정수여야 합니다.") from error

        if not employee_id or not product_id:
            raise ValueError("employee_id와 product_id는 비어 있을 수 없습니다.")
        if state not in {"idle", "running", "paused", "complete"}:
            raise ValueError(f"지원하지 않는 작업 상태입니다: {state}")
        if last_result not in {"waiting", "pass", "fail", "defect"}:
            raise ValueError(f"지원하지 않는 판정 결과입니다: {last_result}")
        if last_result == "defect" and (
            event_name != "manual_defect" or defect_type != "manual"
        ):
            raise ValueError("최종 불량은 manual_defect / manual 정보가 필요합니다.")

        with self.connect() as connection:
            employee = connection.execute(
                "SELECT role FROM employees WHERE employee_id = ?", (employee_id,)
            ).fetchone()
            if employee is None or employee["role"] != "worker":
                raise ValueError("사용할 수 없는 작업자 계정입니다.")
            product = connection.execute(
                "SELECT product_name, total_steps FROM products WHERE product_id = ?",
                (product_id,),
            ).fetchone()
            if product is None:
                raise ValueError(f"등록되지 않은 제품입니다: {product_id}")
            registered_total_steps = int(product["total_steps"])
            if total_steps != registered_total_steps:
                raise ValueError(
                    f"전체 STEP 수가 등록 정보와 다릅니다: "
                    f"수신 {total_steps}, 등록 {registered_total_steps}"
                )
            minimum_step = 0 if state == "idle" else 1
            if current_step < minimum_step or current_step > total_steps:
                raise ValueError(
                    f"current_step은 {minimum_step}~{total_steps} 범위여야 합니다."
                )
            if state == "complete" and current_step != total_steps:
                raise ValueError("완료 상태의 current_step은 마지막 STEP이어야 합니다.")

            event_values = (
                employee_id, product_id, product_name or str(product["product_name"]),
                state, current_step, total_steps, last_result, event_name, defect_type, detail,
            )
            latest_event = connection.execute(
                """SELECT employee_id, product_id, product_name, state,
                          current_step, total_steps, last_result, event, defect_type, detail
                   FROM worker_state_events
                   WHERE employee_id = ?
                   ORDER BY state_event_id DESC LIMIT 1""",
                (employee_id,),
            ).fetchone()
            # 일반 상태와 동일 PASS 재전송은 중복 억제합니다. 같은 STEP의 반복 FAIL은
            # 재검사 횟수 자체가 품질 지표이므로 수신 건마다 별도 판정으로 기록합니다.
            if (latest_event is not None and tuple(latest_event) == event_values
                    and last_result != "fail"):
                return None
            cursor = connection.execute(
                """INSERT INTO worker_state_events(
                       employee_id, product_id, product_name, state,
                       current_step, total_steps, last_result, event, defect_type,
                       detail, received_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '+9 hours'))""",
                event_values,
            )
            event_id = int(cursor.lastrowid)

            # idle은 작업 선택/초기화 상태이므로 원문만 기록하고 작업시간은 시작하지 않습니다.
            if state == "idle":
                return event_id

            product_run = connection.execute(
                """SELECT product_run_id, product_id FROM product_runs
                   WHERE employee_id = ? AND completed_at IS NULL
                   ORDER BY started_at DESC, product_run_id DESC LIMIT 1""",
                (employee_id,),
            ).fetchone()
            if product_run is not None and str(product_run["product_id"]) != product_id:
                raise ValueError("다른 제품의 미완료 작업이 이미 존재합니다.")
            if product_run is None:
                product_run_id = int(connection.execute(
                    """INSERT INTO product_runs(
                           employee_id, product_id, started_at, completed_at
                       ) VALUES (?, ?, datetime('now', '+9 hours'), NULL)""",
                    (employee_id, product_id),
                ).lastrowid)
            else:
                product_run_id = int(product_run["product_run_id"])

            # STEP 전환 메시지의 PASS는 새 STEP이 아니라 방금 끝난 이전 STEP의
            # 검사 결과이므로, STEP을 닫기 전에 판정 연결 대상을 기억합니다.
            previous_step_run = connection.execute(
                """SELECT step_run_id, step_no FROM step_runs
                   WHERE product_run_id = ?
                   ORDER BY step_no DESC, step_run_id DESC LIMIT 1""",
                (product_run_id,),
            ).fetchone()

            # 다음 STEP 메시지가 오면 이전 STEP의 작업시간을 완료합니다.
            connection.execute(
                """UPDATE pause_logs SET resumed_at = datetime('now', '+9 hours')
                   WHERE resumed_at IS NULL AND step_run_id IN (
                       SELECT step_run_id FROM step_runs
                       WHERE product_run_id = ? AND step_no < ?
                   )""",
                (product_run_id, current_step),
            )
            connection.execute(
                """UPDATE step_runs SET completed_at = datetime('now', '+9 hours')
                   WHERE product_run_id = ? AND step_no < ?
                     AND completed_at IS NULL""",
                (product_run_id, current_step),
            )

            step_run = connection.execute(
                """SELECT step_run_id FROM step_runs
                   WHERE product_run_id = ? AND step_no = ?
                   ORDER BY step_run_id DESC LIMIT 1""",
                (product_run_id, current_step),
            ).fetchone()
            if step_run is None:
                step_run_id = int(connection.execute(
                    """INSERT INTO step_runs(
                           product_run_id, step_no, started_at, completed_at
                       ) VALUES (?, ?, datetime('now', '+9 hours'), NULL)""",
                    (product_run_id, current_step),
                ).lastrowid)
            else:
                step_run_id = int(step_run["step_run_id"])

            # 작업자는 중간 STEP 통과 시 last_result=waiting과 event=step_pass를
            # 전송하므로 이를 직전 STEP의 PASS 판정으로 해석합니다. 마지막 STEP의
            # complete+pass는 검사 PASS와 정상 완성품을 각각 1건씩 반영합니다.
            judgement_result = (
                "pass" if event_name == "step_pass" else last_result
            )
            judgement_step_run_id = step_run_id
            if (
                judgement_result == "pass"
                and previous_step_run is not None
                and int(previous_step_run["step_no"]) < current_step
            ):
                judgement_step_run_id = int(previous_step_run["step_run_id"])
            if judgement_result in {"pass", "fail"}:
                connection.execute(
                    """INSERT INTO judgement_logs(
                           step_run_id, result, source, detail, judged_at
                       ) VALUES (?, ?, ?, ?, datetime('now', '+9 hours'))""",
                    (
                        judgement_step_run_id, judgement_result,
                        event_name or "inspection", detail,
                    ),
                )

            if state == "paused":
                open_pause = connection.execute(
                    """SELECT pause_id FROM pause_logs
                       WHERE step_run_id = ? AND resumed_at IS NULL LIMIT 1""",
                    (step_run_id,),
                ).fetchone()
                if open_pause is None:
                    connection.execute(
                        """INSERT INTO pause_logs(step_run_id, paused_at, resumed_at)
                           VALUES (?, datetime('now', '+9 hours'), NULL)""",
                        (step_run_id,),
                    )
            else:
                connection.execute(
                    """UPDATE pause_logs SET resumed_at = datetime('now', '+9 hours')
                       WHERE step_run_id = ? AND resumed_at IS NULL""",
                    (step_run_id,),
                )

            # 수동 불량 등록만 현재 STEP과 제품 작업을 defect 상태로 종료합니다.
            # AI fail은 재검사 대상이므로 현재 STEP과 제품 작업을 계속 유지합니다.
            if last_result == "defect":
                connection.execute(
                    """UPDATE pause_logs SET resumed_at = datetime('now', '+9 hours')
                       WHERE resumed_at IS NULL AND step_run_id IN (
                           SELECT step_run_id FROM step_runs
                           WHERE product_run_id = ?
                       )""",
                    (product_run_id,),
                )
                connection.execute(
                    """UPDATE step_runs SET completed_at = datetime('now', '+9 hours')
                       WHERE product_run_id = ? AND completed_at IS NULL""",
                    (product_run_id,),
                )
                connection.execute(
                    """INSERT OR IGNORE INTO defect_logs(
                           step_run_id, defect_type, detail, defect_at
                       ) VALUES (?, ?, ?, datetime('now', '+9 hours'))""",
                    (step_run_id, defect_type, detail),
                )
                connection.execute(
                    """UPDATE product_runs
                       SET completed_at = datetime('now', '+9 hours'), result = 'defect'
                       WHERE product_run_id = ? AND completed_at IS NULL""",
                    (product_run_id,),
                )
                return event_id

            if state == "complete":
                connection.execute(
                    """UPDATE step_runs SET completed_at = datetime('now', '+9 hours')
                       WHERE product_run_id = ? AND completed_at IS NULL""",
                    (product_run_id,),
                )
                connection.execute(
                    """UPDATE product_runs
                       SET completed_at = datetime('now', '+9 hours'), result = 'pass'
                       WHERE product_run_id = ? AND completed_at IS NULL""",
                    (product_run_id,),
                )
            return event_id

    def search_employees(self, keyword: str = "") -> list[dict]:
        """직원 검색 결과와 현재 출근·공정 진행 상태를 함께 조회합니다."""
        search_text = f"%{keyword.strip()}%"
        with self.connect() as connection:
            rows = connection.execute(
                EMPLOYEE_MONITORING_SELECT + """
                WHERE e.role IN ('admin', 'worker')
                  AND (e.employee_id LIKE ? OR e.name LIKE ?)
                ORDER BY e.employee_id""",
                (search_text, search_text),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_employee_monitoring_rows(self, employee_ids: set[str]) -> list[dict]:
        """변경된 직원들의 출근·진행 제품·현재 STEP만 한 번에 조회합니다."""
        cleaned_ids = sorted({str(item).strip() for item in employee_ids if str(item).strip()})
        if not cleaned_ids:
            return []
        placeholders = ",".join("?" for _item in cleaned_ids)
        with self.connect() as connection:
            rows = connection.execute(
                EMPLOYEE_MONITORING_SELECT + f"""
                WHERE e.role IN ('admin', 'worker')
                  AND e.employee_id IN ({placeholders})
                ORDER BY e.employee_id""",
                cleaned_ids,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_working_worker_count(self) -> int:
        """현재 열린 출근 기록이 있는 작업자 수를 조회합니다."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT COUNT(*) FROM employees AS e
                   WHERE e.role = 'worker' AND EXISTS (
                       SELECT 1 FROM work_sessions AS ws
                       WHERE ws.employee_id = e.employee_id
                         AND ws.login_at IS NOT NULL
                         AND ws.logout_at IS NULL
                   )"""
            ).fetchone()
        return int(row[0])

    def get_employee_counts(self) -> dict:
        """직원 현황 카드에 필요한 계정·출근 수를 한 번에 집계합니다."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT
                       COUNT(*) AS total_count,
                       SUM(CASE WHEN e.role = 'worker' THEN 1 ELSE 0 END)
                           AS worker_count,
                       SUM(CASE WHEN e.role = 'admin' THEN 1 ELSE 0 END)
                           AS admin_count,
                       SUM(CASE WHEN e.role = 'worker' AND EXISTS (
                           SELECT 1 FROM work_sessions AS ws
                           WHERE ws.employee_id = e.employee_id
                             AND ws.login_at IS NOT NULL
                             AND ws.logout_at IS NULL
                       ) THEN 1 ELSE 0 END) AS working_worker_count
                   FROM employees AS e
                   WHERE e.role IN ('admin', 'worker')"""
            ).fetchone()
        return {key: int(row[key] or 0) for key in row.keys()}

    def get_employee(self, employee_id: str) -> Optional[dict]:
        """직원 기본정보를 조회합니다."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT employee_id, name, COALESCE(role, '') AS role
                   FROM employees WHERE employee_id = ?""",
                (employee_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_worker(self, employee_id: str, name: str, password: str) -> None:
        """관리자 화면에서 role이 worker로 고정된 작업자 계정을 생성합니다."""
        cleaned_id = employee_id.strip()
        cleaned_name = name.strip()
        if not cleaned_id or not cleaned_name:
            raise ValueError("직원번호와 이름은 비어 있을 수 없습니다.")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO employees(employee_id, name, password_hash, role)
                   VALUES (?, ?, ?, ?)""",
                (cleaned_id, cleaned_name, self.hash_password(password), "worker"),
            )

    def revoke_worker(self, employee_id: str) -> dict:
        """작업 이력을 보존하면서 작업자 계정의 로그인 권한을 말소합니다."""
        cleaned_id = employee_id.strip()
        if not cleaned_id:
            raise ValueError("직원번호는 비어 있을 수 없습니다.")
        replacement_hash = self.hash_password(os.urandom(32).hex())
        with self.connect() as connection:
            employee = connection.execute(
                "SELECT employee_id, name, role FROM employees WHERE employee_id = ?",
                (cleaned_id,),
            ).fetchone()
            if employee is None:
                raise ValueError("해당 직원번호의 계정을 찾을 수 없습니다.")
            if employee["role"] != "worker":
                raise ValueError("작업자 계정만 말소할 수 있습니다.")
            connection.execute(
                """UPDATE work_sessions SET logout_at = datetime('now', '+9 hours')
                   WHERE employee_id = ? AND logout_at IS NULL""",
                (cleaned_id,),
            )
            connection.execute(
                """UPDATE employees SET role = 'revoked', password_hash = ?
                   WHERE employee_id = ?""",
                (replacement_hash, cleaned_id),
            )
        return {"employee_id": employee["employee_id"], "name": employee["name"]}

    def search_products(self, keyword: str = "") -> list[dict]:
        """제품의 생산 결과와 검사 PASS/FAIL 요약을 함께 조회합니다."""
        search_text = f"%{keyword.strip()}%"
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT p.product_id, p.product_name, p.total_steps,
                          SUM(CASE WHEN pr.completed_at IS NOT NULL THEN 1 ELSE 0 END)
                              AS completed_count,
                          SUM(CASE WHEN pr.result = 'defect' THEN 1 ELSE 0 END)
                              AS defect_count,
                           CASE WHEN SUM(CASE WHEN pr.completed_at IS NOT NULL
                                             THEN 1 ELSE 0 END) = 0 THEN 0.0
                               ELSE ROUND(
                                   100.0 * SUM(CASE WHEN pr.result = 'defect'
                                                    THEN 1 ELSE 0 END)
                                   / SUM(CASE WHEN pr.completed_at IS NOT NULL
                                              THEN 1 ELSE 0 END), 1)
                           END AS defect_rate
                   FROM products AS p
                   LEFT JOIN product_runs AS pr
                     ON pr.product_id = p.product_id
                    AND pr.product_run_id > COALESCE((
                        SELECT qb.product_run_id_cutoff
                        FROM product_quality_baselines AS qb
                        WHERE qb.product_id = p.product_id
                    ), 0)
                   WHERE p.product_id LIKE ? OR p.product_name LIKE ?
                   GROUP BY p.product_id, p.product_name, p.total_steps
                   ORDER BY p.product_id""",
                (search_text, search_text),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_product(self, product_id: str) -> Optional[dict]:
        """제품번호로 제품 기본정보를 조회합니다."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT product_id, product_name, total_steps
                   FROM products WHERE product_id = ?""",
                (product_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_product(self, product_id: str, product_name: str,
                       total_steps: int) -> None:
        """관리자가 새 제품과 전체 STEP 수를 등록합니다."""
        cleaned_id = product_id.strip()
        cleaned_name = product_name.strip()
        if not cleaned_id or not cleaned_name:
            raise ValueError("제품번호와 제품명은 비어 있을 수 없습니다.")
        if int(total_steps) < 1:
            raise ValueError("전체 STEP은 1 이상이어야 합니다.")
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO products(product_id, product_name, total_steps)
                   VALUES (?, ?, ?)""",
                (cleaned_id, cleaned_name, int(total_steps)),
            )

    def update_product(self, product_id: str, product_name: str,
                       total_steps: int) -> None:
        """기존 제품명과 전체 STEP 수를 수정합니다."""
        cleaned_name = product_name.strip()
        if not cleaned_name:
            raise ValueError("제품명은 비어 있을 수 없습니다.")
        if int(total_steps) < 1:
            raise ValueError("전체 STEP은 1 이상이어야 합니다.")
        with self.connect() as connection:
            cursor = connection.execute(
                """UPDATE products SET product_name = ?, total_steps = ?
                   WHERE product_id = ?""",
                (cleaned_name, int(total_steps), product_id),
            )
            if cursor.rowcount == 0:
                raise ValueError("수정할 제품을 찾을 수 없습니다.")

    def delete_product(self, product_id: str) -> None:
        """작업 이력이 없는 제품을 삭제합니다."""
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM product_quality_baselines WHERE product_id = ?", (product_id,)
            )
            cursor = connection.execute(
                "DELETE FROM products WHERE product_id = ?", (product_id,)
            )
            if cursor.rowcount == 0:
                raise ValueError("삭제할 제품을 찾을 수 없습니다.")

    def get_work_sessions(self, employee_id: str) -> list[dict]:
        """직원의 출퇴근 시각, 경과 근무시간과 9시간 충족 여부를 조회합니다."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT session_id, login_at, logout_at,
                          CASE WHEN login_at IS NULL THEN NULL
                               ELSE MAX(0, CAST(ROUND(
                                   (julianday(COALESCE(
                                       logout_at, datetime('now', '+9 hours')
                                   )) - julianday(login_at)) * 86400
                               ) AS INTEGER))
                          END AS worked_seconds,
                          CASE WHEN logout_at IS NULL THEN 'working'
                               WHEN login_at IS NOT NULL AND ROUND(
                                   (julianday(logout_at) - julianday(login_at)) * 86400
                               ) >= ? THEN 'normal'
                               ELSE 'short'
                          END AS work_status
                   FROM work_sessions
                   WHERE employee_id = ? ORDER BY login_at DESC, session_id DESC""",
                (STANDARD_WORK_SECONDS, employee_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_product_runs(self, employee_id: str) -> list[dict]:
        """직원이 작업한 제품 기록과 회차별 검사 FAIL 횟수를 조회합니다."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT pr.product_run_id, pr.product_id,
                          COALESCE(p.product_name, pr.product_id) AS product_name,
                          (SELECT COUNT(*)
                           FROM judgement_logs AS jl
                           JOIN step_runs AS jsr
                             ON jsr.step_run_id = jl.step_run_id
                           WHERE jsr.product_run_id = pr.product_run_id
                             AND jl.result = 'fail') AS fail_count,
                          pr.started_at, pr.completed_at, pr.result
                   FROM product_runs AS pr
                   LEFT JOIN products AS p ON p.product_id = pr.product_id
                   WHERE pr.employee_id = ?
                   ORDER BY pr.started_at DESC, pr.product_run_id DESC""",
                (employee_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_defect_logs(self, employee_id: str) -> list[dict]:
        """직원이 등록한 불량 제품과 발생 STEP을 최신순으로 조회합니다."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT dl.defect_id, pr.product_run_id, pr.product_id,
                          COALESCE(p.product_name, pr.product_id) AS product_name,
                          sr.step_no, dl.defect_type, dl.detail, dl.defect_at
                   FROM defect_logs AS dl
                   JOIN step_runs AS sr ON sr.step_run_id = dl.step_run_id
                   JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id
                   LEFT JOIN products AS p ON p.product_id = pr.product_id
                   WHERE pr.employee_id = ?
                   ORDER BY dl.defect_at DESC, dl.defect_id DESC""",
                (employee_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_step_runs(self, product_run_id: int) -> list[dict]:
        """STEP 작업시간과 해당 작업 회차의 PASS/FAIL 판정을 조회합니다."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT sr.step_run_id, sr.step_no, sr.started_at, sr.completed_at,
                          CASE WHEN sr.started_at IS NULL OR sr.completed_at IS NULL THEN NULL
                          ELSE MAX(0, CAST(ROUND(
                              (julianday(sr.completed_at) - julianday(sr.started_at)) * 86400
                              - COALESCE(SUM(CASE WHEN pl.paused_at IS NOT NULL
                                                  AND pl.resumed_at IS NOT NULL
                                  THEN (julianday(pl.resumed_at) - julianday(pl.paused_at)) * 86400
                                  ELSE 0 END), 0)) AS INTEGER)) END AS actual_seconds,
                          (SELECT COUNT(*) FROM judgement_logs AS jl
                           WHERE jl.step_run_id = sr.step_run_id AND jl.result = 'pass')
                              AS pass_count,
                          (SELECT COUNT(*) FROM judgement_logs AS jl
                           WHERE jl.step_run_id = sr.step_run_id AND jl.result = 'fail')
                              AS fail_count,
                          CASE WHEN (SELECT COUNT(*) FROM judgement_logs AS jl
                                          WHERE jl.step_run_id = sr.step_run_id) = 0 THEN 0.0
                               ELSE ROUND(
                                   100.0 * (SELECT COUNT(*) FROM judgement_logs AS jl
                                            WHERE jl.step_run_id = sr.step_run_id
                                              AND jl.result = 'fail')
                                   / (SELECT COUNT(*) FROM judgement_logs AS jl
                                      WHERE jl.step_run_id = sr.step_run_id), 1)
                          END AS fail_rate
                   FROM step_runs AS sr
                   LEFT JOIN pause_logs AS pl ON pl.step_run_id = sr.step_run_id
                   WHERE sr.product_run_id = ?
                   GROUP BY sr.step_run_id, sr.step_no, sr.started_at, sr.completed_at
                   ORDER BY sr.step_no, sr.step_run_id""",
                (product_run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_product_step_quality_summary(self, product_id: str) -> list[dict]:
        """제품의 STEP별 검사 판정과 수동 불량 등록 횟수를 조회합니다."""
        product = self.get_product(product_id)
        if product is None:
            raise ValueError("제품을 찾을 수 없습니다.")
        baseline = self.get_product_quality_baseline(product_id)
        judgement_cutoff = int(baseline["judgement_id_cutoff"]) if baseline else 0
        defect_cutoff = int(baseline["defect_id_cutoff"]) if baseline else 0
        with self.connect() as connection:
            judgement_rows = connection.execute(
                """SELECT sr.step_no,
                          COUNT(*) AS judgement_count,
                          SUM(CASE WHEN jl.result = 'pass' THEN 1 ELSE 0 END) AS pass_count,
                          SUM(CASE WHEN jl.result = 'fail' THEN 1 ELSE 0 END) AS fail_count,
                          ROUND(100.0 * SUM(CASE WHEN jl.result = 'fail' THEN 1 ELSE 0 END)
                                / COUNT(*), 1) AS fail_rate,
                          MAX(CASE WHEN jl.result = 'fail' THEN jl.judged_at END)
                              AS latest_fail_at
                   FROM judgement_logs AS jl
                   JOIN step_runs AS sr ON sr.step_run_id = jl.step_run_id
                   JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id
                   WHERE pr.product_id = ? AND jl.judgement_id > ?
                   GROUP BY sr.step_no
                   ORDER BY sr.step_no""",
                (product_id, judgement_cutoff),
            ).fetchall()
            defect_rows = connection.execute(
                """SELECT sr.step_no, COUNT(*) AS defect_button_count,
                          MAX(dl.defect_at) AS latest_defect_at
                   FROM defect_logs AS dl
                   JOIN step_runs AS sr ON sr.step_run_id = dl.step_run_id
                   JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id
                   WHERE pr.product_id = ? AND dl.defect_id > ?
                   GROUP BY sr.step_no
                   ORDER BY sr.step_no""",
                (product_id, defect_cutoff),
            ).fetchall()
        by_step = {int(row["step_no"]): dict(row) for row in judgement_rows}
        for row in defect_rows:
            step_no = int(row["step_no"])
            by_step.setdefault(step_no, {
                "step_no": step_no,
                "judgement_count": 0,
                "pass_count": 0,
                "fail_count": 0,
                "fail_rate": 0.0,
                "latest_fail_at": None,
            })
            by_step[step_no]["defect_button_count"] = int(row["defect_button_count"])
            by_step[step_no]["latest_defect_at"] = row["latest_defect_at"]
        result = []
        for step_no in range(1, int(product["total_steps"]) + 1):
            item = by_step.get(step_no, {
                "step_no": step_no,
                "judgement_count": 0,
                "pass_count": 0,
                "fail_count": 0,
                "fail_rate": 0.0,
                "latest_fail_at": None,
            })
            item.setdefault("defect_button_count", 0)
            item.setdefault("latest_defect_at", None)
            result.append(item)
        return result

    def get_product_quality_baseline(self, product_id: str) -> Optional[dict]:
        """제품 품질 집계의 마지막 초기화 기준을 조회합니다."""
        with self.connect() as connection:
            row = connection.execute(
                """SELECT product_id, reset_at, product_run_id_cutoff,
                          judgement_id_cutoff, defect_id_cutoff
                   FROM product_quality_baselines WHERE product_id = ?""",
                (product_id,),
            ).fetchone()
        return dict(row) if row else None

    def reset_product_quality_baseline(self, product_id: str) -> str:
        """과거 이력을 보존하고 현재 ID 이후부터 제품 품질을 새로 집계합니다."""
        with self.connect() as connection:
            product = connection.execute(
                "SELECT 1 FROM products WHERE product_id = ?", (product_id,)
            ).fetchone()
            if product is None:
                raise ValueError("제품을 찾을 수 없습니다.")
            active_run = connection.execute(
                """SELECT 1 FROM product_runs
                   WHERE product_id = ? AND completed_at IS NULL LIMIT 1""",
                (product_id,),
            ).fetchone()
            if active_run is not None:
                raise ValueError("진행 중인 제품 작업이 있어 품질 집계를 초기화할 수 없습니다.")
            product_run_cutoff = connection.execute(
                "SELECT COALESCE(MAX(product_run_id), 0) FROM product_runs WHERE product_id = ?",
                (product_id,),
            ).fetchone()[0]
            judgement_cutoff = connection.execute(
                """SELECT COALESCE(MAX(jl.judgement_id), 0)
                   FROM judgement_logs AS jl
                   JOIN step_runs AS sr ON sr.step_run_id = jl.step_run_id
                   JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id
                   WHERE pr.product_id = ?""",
                (product_id,),
            ).fetchone()[0]
            defect_cutoff = connection.execute(
                """SELECT COALESCE(MAX(dl.defect_id), 0)
                   FROM defect_logs AS dl
                   JOIN step_runs AS sr ON sr.step_run_id = dl.step_run_id
                   JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id
                   WHERE pr.product_id = ?""",
                (product_id,),
            ).fetchone()[0]
            connection.execute(
                """INSERT OR REPLACE INTO product_quality_baselines(
                       product_id, reset_at, product_run_id_cutoff,
                       judgement_id_cutoff, defect_id_cutoff
                   ) VALUES (?, datetime('now', '+9 hours'), ?, ?, ?)""",
                (product_id, product_run_cutoff, judgement_cutoff, defect_cutoff),
            )
            reset_at = connection.execute(
                "SELECT reset_at FROM product_quality_baselines WHERE product_id = ?",
                (product_id,),
            ).fetchone()["reset_at"]
        return str(reset_at)

    def get_pause_logs(self, step_run_id: int) -> list[dict]:
        """특정 STEP의 Pause/Resume 시각과 정지 시간을 조회합니다."""
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT pause_id, paused_at, resumed_at,
                          CASE WHEN paused_at IS NULL OR resumed_at IS NULL THEN NULL
                               ELSE MAX(0, CAST(ROUND(
                                   (julianday(resumed_at) - julianday(paused_at)) * 86400
                               ) AS INTEGER))
                          END AS pause_seconds
                   FROM pause_logs
                   WHERE step_run_id = ? ORDER BY paused_at, pause_id""",
                (step_run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def insert_sample_data(self) -> None:
        """개발 테스트용 샘플 데이터를 중복 없이 추가합니다."""
        with self.connect() as connection:
            for values in (
                ("admin", "관리자", self.hash_password("admin1234"), "admin"),
                ("1001", "홍길동", self.hash_password("worker1234"), "worker"),
            ):
                connection.execute(
                    "INSERT OR IGNORE INTO employees(employee_id, name, password_hash, role) VALUES (?, ?, ?, ?)",
                    values,
                )
            connection.execute(
                "INSERT OR IGNORE INTO products(product_id, product_name, total_steps) VALUES (?, ?, ?)",
                ("P001", "샘플 제품", 2),
            )
            if not connection.execute(
                "SELECT 1 FROM work_sessions WHERE employee_id = ? LIMIT 1", ("1001",)
            ).fetchone():
                connection.execute(
                    "INSERT INTO work_sessions(employee_id, login_at, logout_at) VALUES (?, ?, ?)",
                    ("1001", "2026-08-31 09:00:00", "2026-08-31 18:00:00"),
                )
            if not connection.execute(
                "SELECT 1 FROM product_runs WHERE employee_id = ? LIMIT 1", ("1001",)
            ).fetchone():
                product_run_id = connection.execute(
                    """INSERT INTO product_runs(
                           employee_id, product_id, started_at, completed_at, result
                       ) VALUES (?, ?, ?, ?, ?)""",
                    ("1001", "P001", "2026-08-31 10:00:00",
                     "2026-08-31 11:10:00", "pass"),
                ).lastrowid
                step_one = connection.execute(
                    "INSERT INTO step_runs(product_run_id, step_no, started_at, completed_at) VALUES (?, ?, ?, ?)",
                    (product_run_id, 1, "2026-08-31 10:00:00", "2026-08-31 10:30:00"),
                ).lastrowid
                connection.execute(
                    "INSERT INTO pause_logs(step_run_id, paused_at, resumed_at) VALUES (?, ?, ?)",
                    (step_one, "2026-08-31 10:10:00", "2026-08-31 10:15:00"),
                )
                connection.execute(
                    "INSERT INTO step_runs(product_run_id, step_no, started_at, completed_at) VALUES (?, ?, ?, ?)",
                    (product_run_id, 2, "2026-08-31 10:35:00", "2026-08-31 11:10:00"),
                )

    @staticmethod
    def format_seconds(seconds: Optional[int]) -> str:
        """초 단위 시간을 사용자가 읽기 쉬운 HH:MM:SS로 변환합니다."""
        if seconds is None:
            return "진행 중"
        hours, remainder = divmod(max(0, int(seconds)), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
