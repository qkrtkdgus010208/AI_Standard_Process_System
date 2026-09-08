"""SQLite schema creation and data migrations for the monitoring database."""

from __future__ import annotations

import sqlite3


class DatabaseSchemaManager:
    """Owns database DDL and one-time migrations.

    The schema manager deliberately receives an already configured connection;
    it does not import or depend on :class:`DatabaseManager`.
    """

    def initialize(self, connection: sqlite3.Connection) -> None:
        """Create the schema and apply all compatible migrations."""
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
            CREATE TABLE IF NOT EXISTS product_step_guides (
                product_id TEXT NOT NULL,
                step_no INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                mime_type TEXT NOT NULL DEFAULT 'image/jpeg',
                byte_size INTEGER NOT NULL DEFAULT 0,
                sha256 TEXT NOT NULL DEFAULT '',
                updated_at DATETIME NOT NULL DEFAULT (datetime('now', '+9 hours')),
                PRIMARY KEY (product_id, step_no),
                FOREIGN KEY (product_id) REFERENCES products(product_id)
                    ON DELETE CASCADE
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
                client_event_id TEXT,
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
        self.migrate_normalized_quality_logs(connection)
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
        if "client_event_id" not in worker_event_columns:
            connection.execute(
                "ALTER TABLE worker_state_events ADD COLUMN client_event_id TEXT"
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
            CREATE INDEX IF NOT EXISTS idx_judgement_logs_step_result
                ON judgement_logs(step_run_id, result);
            CREATE INDEX IF NOT EXISTS idx_step_runs_product_run_step_no
                ON step_runs(product_run_id, step_no);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_worker_state_events_client_event
                ON worker_state_events(employee_id, client_event_id)
                WHERE client_event_id IS NOT NULL;
            """
        )
        connection.execute(
            """UPDATE product_runs SET result = 'pass'
               WHERE completed_at IS NOT NULL AND result = 'in_progress'"""
        )
        self.migrate_legacy_utc_timestamps(connection)

    @staticmethod
    def migrate_normalized_quality_logs(connection: sqlite3.Connection) -> None:
        """Remove derivable duplicate quality-log keys while preserving history."""
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
    def migrate_legacy_utc_timestamps(connection: sqlite3.Connection) -> None:
        """Convert legacy UTC records to KST once."""
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
