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
from db.database_schema import DatabaseSchemaManager
from db.employee_repository import EmployeeRepository
from db.product_repository import ProductRepository
from db.work_history_repository import WorkHistoryRepository
from models.state_types import WorkerStateInput
from services.time_utils import format_seconds
from services.worker_state_recorder import WorkerStateRecorder

DEFAULT_DB_PATH = config.DATABASE_PATH
PASSWORD_ITERATIONS = 260_000
STANDARD_WORK_SECONDS = 9 * 60 * 60


class DatabaseManager:
    """UI와 저장소 사이의 호환 facade입니다."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = str(Path(db_path).resolve())
        self._employee_repository = EmployeeRepository(
            self.connect, self.verify_password, self.hash_password
        )
        self._product_repository = ProductRepository(self.connect)
        self._work_history_repository = WorkHistoryRepository(
            self.connect, STANDARD_WORK_SECONDS
        )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Foreign Key가 활성화된 연결을 만들고 안전하게 닫습니다."""
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA temp_store = MEMORY")
        connection.execute("PRAGMA cache_size = -64000")
        connection.execute("PRAGMA mmap_size = 268435456")
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
            DatabaseSchemaManager().initialize(connection)

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

    def record_worker_state(self, state_data: WorkerStateInput) -> Optional[int]:
        """수신 상태를 원자적으로 저장하고 공정 이력에 반영합니다."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            recorder = WorkerStateRecorder(connection)
            return recorder.record(state_data)

    def verify_admin_login(self, employee_id: str, password: str) -> Optional[dict]:
        return self._employee_repository.verify_admin_login(employee_id, password)

    def verify_worker_login(self, employee_id: str, password: str) -> Optional[dict]:
        return self._employee_repository.verify_worker_login(employee_id, password)

    def start_work_session(self, employee_id: str) -> int:
        return self._work_history_repository.start_work_session(employee_id)

    def end_work_session(self, employee_id: str) -> None:
        return self._work_history_repository.end_work_session(employee_id)

    def get_incomplete_work_state(self, employee_id: str) -> Optional[dict]:
        return self._work_history_repository.get_incomplete_work_state(employee_id)

    def search_employees(self, keyword: str = "") -> list[dict]:
        return self._employee_repository.search_employees(keyword)

    def get_employee_monitoring_rows(self, employee_ids: set[str]) -> list[dict]:
        return self._employee_repository.get_employee_monitoring_rows(employee_ids)

    def get_working_worker_count(self) -> int:
        return self._employee_repository.get_working_worker_count()

    def get_employee_counts(self) -> dict:
        return self._employee_repository.get_employee_counts()

    def get_employee(self, employee_id: str) -> Optional[dict]:
        return self._employee_repository.get_employee(employee_id)

    def create_worker(self, employee_id: str, name: str, password: str) -> None:
        return self._employee_repository.create_worker(employee_id, name, password)

    def revoke_worker(self, employee_id: str) -> dict:
        return self._employee_repository.revoke_worker(employee_id)

    def search_products(self, keyword: str = "") -> list[dict]:
        return self._product_repository.search_products(keyword)

    def list_products(self) -> list[dict]:
        return self._product_repository.list_products()

    def get_product(self, product_id: str) -> Optional[dict]:
        return self._product_repository.get_product(product_id)

    def get_product_step_guides(self, product_id: str) -> list[dict]:
        return self._product_repository.get_product_step_guides(product_id)

    def get_product_step_guide(self, product_id: str, step_no: int) -> Optional[dict]:
        return self._product_repository.get_product_step_guide(product_id, step_no)

    def replace_product_step_guides(self, product_id: str, guides: list[dict]) -> None:
        return self._product_repository.replace_product_step_guides(product_id, guides)

    def create_product(self, product_id: str, product_name: str, total_steps: int) -> None:
        return self._product_repository.create_product(product_id, product_name, total_steps)

    def update_product(self, product_id: str, product_name: str, total_steps: int) -> None:
        return self._product_repository.update_product(product_id, product_name, total_steps)

    def delete_product(self, product_id: str) -> None:
        return self._product_repository.delete_product(product_id)

    def get_work_sessions(self, employee_id: str) -> list[dict]:
        return self._work_history_repository.get_work_sessions(employee_id)

    def get_product_runs(self, employee_id: str) -> list[dict]:
        return self._work_history_repository.get_product_runs(employee_id)

    def get_defect_logs(self, employee_id: str) -> list[dict]:
        return self._work_history_repository.get_defect_logs(employee_id)

    def get_step_runs(self, product_run_id: int) -> list[dict]:
        return self._work_history_repository.get_step_runs(product_run_id)

    def get_product_step_quality_summary(self, product_id: str) -> list[dict]:
        return self._product_repository.get_product_step_quality_summary(product_id)

    def get_product_quality_baseline(self, product_id: str) -> Optional[dict]:
        return self._product_repository.get_product_quality_baseline(product_id)

    def reset_product_quality_baseline(self, product_id: str) -> str:
        return self._product_repository.reset_product_quality_baseline(product_id)

    def get_pause_logs(self, step_run_id: int) -> list[dict]:
        return self._work_history_repository.get_pause_logs(step_run_id)

    def get_employee_pause_logs(self, employee_id: str) -> list[dict]:
        return self._work_history_repository.get_employee_pause_logs(employee_id)

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
                    (
                        "1001",
                        "P001",
                        "2026-08-31 10:00:00",
                        "2026-08-31 11:10:00",
                        "pass",
                    ),
                ).lastrowid
                step_one = connection.execute(
                    """INSERT INTO step_runs(
                           product_run_id, step_no, started_at, completed_at
                       ) VALUES (?, ?, ?, ?)""",
                    (
                        product_run_id,
                        1,
                        "2026-08-31 10:00:00",
                        "2026-08-31 10:30:00",
                    ),
                ).lastrowid
                connection.execute(
                    """INSERT INTO pause_logs(step_run_id, paused_at, resumed_at)
                       VALUES (?, ?, ?)""",
                    (step_one, "2026-08-31 10:10:00", "2026-08-31 10:15:00"),
                )
                connection.execute(
                    """INSERT INTO step_runs(
                           product_run_id, step_no, started_at, completed_at
                       ) VALUES (?, ?, ?, ?)""",
                    (
                        product_run_id,
                        2,
                        "2026-08-31 10:35:00",
                        "2026-08-31 11:10:00",
                    ),
                )

    format_seconds = staticmethod(format_seconds)
