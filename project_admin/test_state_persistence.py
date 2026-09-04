import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from database_manager import DatabaseManager
from monitoring_gateway import MonitoringGatewayThread
from tcp_client import TcpClient, WorkerEndpointRegistry


class WorkerStatePersistenceTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = DatabaseManager(
            Path(self.temporary_directory.name) / "test_factory.db"
        )
        self.database.initialize_database()
        self.database.create_worker("1001", "홍길동", "worker1234")
        self.database.create_product("P001", "스마트 액추에이터 A", 5)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def send_state(self, state, current_step, last_result="waiting", event=""):
        return self.database.record_worker_state({
            "employee_id": "1001",
            "product_id": "P001",
            "product_name": "스마트 액추에이터 A",
            "state": state,
            "current_step": current_step,
            "total_steps": 5,
            "last_result": last_result,
            "event": event,
        })

    def test_full_process_is_saved(self):
        self.send_state("idle", 0)
        self.send_state("running", 1)
        self.send_state("running", 1, "fail")
        self.send_state("running", 2)
        self.send_state("paused", 2)
        self.send_state("running", 2)
        self.send_state("running", 3)
        self.send_state("running", 4)
        self.send_state("running", 5)
        self.send_state("complete", 5, "pass")

        with self.database.connect() as connection:
            product_run = connection.execute(
                "SELECT * FROM product_runs WHERE employee_id = '1001'"
            ).fetchone()
            steps = connection.execute(
                "SELECT * FROM step_runs ORDER BY step_no"
            ).fetchall()
            pause = connection.execute("SELECT * FROM pause_logs").fetchone()
            event_count = connection.execute(
                "SELECT COUNT(*) FROM worker_state_events"
            ).fetchone()[0]

        self.assertIsNotNone(product_run["completed_at"])
        self.assertEqual([row["step_no"] for row in steps], [1, 2, 3, 4, 5])
        self.assertTrue(all(row["completed_at"] is not None for row in steps))
        self.assertIsNotNone(pause["resumed_at"])
        self.assertEqual(event_count, 10)

    def test_pause_logs_include_elapsed_seconds(self):
        self.send_state("running", 1)
        self.send_state("paused", 1)
        self.send_state("running", 1)
        with self.database.connect() as connection:
            pause = connection.execute("SELECT pause_id, step_run_id FROM pause_logs").fetchone()
            connection.execute(
                """UPDATE pause_logs
                   SET paused_at = '2026-09-02 10:00:00',
                       resumed_at = '2026-09-02 10:01:15'
                   WHERE pause_id = ?""",
                (pause["pause_id"],),
            )

        pauses = self.database.get_pause_logs(pause["step_run_id"])
        self.assertEqual(pauses[0]["pause_seconds"], 75)

    def test_work_sessions_include_nine_hour_status(self):
        with self.database.connect() as connection:
            normal_id = connection.execute(
                """INSERT INTO work_sessions(employee_id, login_at, logout_at)
                   VALUES ('1001', '2026-09-01 08:00:00', '2026-09-01 17:00:00')"""
            ).lastrowid
            short_id = connection.execute(
                """INSERT INTO work_sessions(employee_id, login_at, logout_at)
                   VALUES ('1001', '2026-09-02 08:00:00', '2026-09-02 16:59:59')"""
            ).lastrowid
            working_id = connection.execute(
                """INSERT INTO work_sessions(employee_id, login_at, logout_at)
                   VALUES ('1001', datetime('now', '+9 hours'), NULL)"""
            ).lastrowid

        sessions = {
            row["session_id"]: row for row in self.database.get_work_sessions("1001")
        }
        self.assertEqual(sessions[normal_id]["worked_seconds"], 9 * 60 * 60)
        self.assertEqual(sessions[normal_id]["work_status"], "normal")
        self.assertEqual(sessions[short_id]["worked_seconds"], 9 * 60 * 60 - 1)
        self.assertEqual(sessions[short_id]["work_status"], "short")
        self.assertEqual(sessions[working_id]["work_status"], "working")

    def test_employee_monitoring_batch_and_counts(self):
        self.database.start_work_session("1001")
        self.send_state("running", 1)

        rows = self.database.get_employee_monitoring_rows({"1001", "", "missing"})
        counts = self.database.get_employee_counts()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["employee_id"], "1001")
        self.assertEqual(rows[0]["attendance_status"], "working")
        self.assertEqual(rows[0]["active_product_name"], "스마트 액추에이터 A")
        self.assertEqual(rows[0]["current_step"], 1)
        self.assertEqual(counts, {
            "total_count": 1,
            "worker_count": 1,
            "admin_count": 0,
            "working_worker_count": 1,
        })

    def test_pass_fail_judgements_are_counted_by_product_and_step(self):
        self.send_state("running", 1, "fail")
        self.send_state("running", 1, "fail")
        self.send_state("running", 2, event="step_pass")
        self.send_state("running", 3, event="step_pass")

        summary = self.database.get_product_step_quality_summary("P001")
        with self.database.connect() as connection:
            product_run_id = connection.execute(
                "SELECT product_run_id FROM product_runs WHERE employee_id = ?",
                ("1001",),
            ).fetchone()["product_run_id"]
        step_runs = self.database.get_step_runs(product_run_id)
        product_runs = self.database.get_product_runs("1001")

        self.assertEqual(summary[0]["judgement_count"], 3)
        self.assertEqual(summary[0]["pass_count"], 1)
        self.assertEqual(summary[0]["fail_count"], 2)
        self.assertAlmostEqual(summary[0]["fail_rate"], 66.7)
        self.assertEqual(step_runs[0]["fail_count"], 2)
        self.assertEqual(step_runs[1]["pass_count"], 1)
        self.assertEqual(product_runs[0]["fail_count"], 2)

    def test_manual_defect_buttons_are_counted_by_product_step(self):
        def register_defect(step_no):
            base = {
                "employee_id": "1001",
                "product_id": "P001",
                "product_name": "스마트 액추에이터 A",
                "state": "running",
                "current_step": step_no,
                "total_steps": 5,
            }
            self.database.record_worker_state({**base, "last_result": "waiting"})
            self.database.record_worker_state({
                **base,
                "last_result": "defect",
                "event": "manual_defect",
                "defect_type": "manual",
                "detail": "작업자 불량 버튼",
            })

        register_defect(2)
        register_defect(2)
        register_defect(3)

        summary = self.database.get_product_step_quality_summary("P001")
        product = self.database.search_products("P001")[0]
        self.assertEqual(summary[1]["defect_button_count"], 2)
        self.assertIsNotNone(summary[1]["latest_defect_at"])
        self.assertEqual(summary[2]["defect_button_count"], 1)
        self.assertEqual(product["defect_count"], 3)

    def test_quality_reset_starts_new_aggregation_without_deleting_history(self):
        self.send_state("running", 1, "fail")
        self.send_state("complete", 5, "pass")
        before_reset = self.database.search_products("P001")[0]
        self.assertEqual(before_reset["completed_count"], 1)
        self.assertEqual(
            self.database.get_product_step_quality_summary("P001")[0]["fail_count"], 1
        )

        reset_at = self.database.reset_product_quality_baseline("P001")

        after_reset = self.database.search_products("P001")[0]
        reset_summary = self.database.get_product_step_quality_summary("P001")
        self.assertTrue(reset_at)
        self.assertEqual(after_reset["completed_count"], 0)
        self.assertEqual(after_reset["defect_count"], 0)
        self.assertTrue(all(row["judgement_count"] == 0 for row in reset_summary))
        with self.database.connect() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM judgement_logs").fetchone()[0], 2
            )

        self.send_state("running", 2, "fail")
        new_summary = self.database.get_product_step_quality_summary("P001")
        self.assertEqual(new_summary[0]["fail_count"], 0)
        self.assertEqual(new_summary[1]["fail_count"], 1)
        with self.assertRaisesRegex(ValueError, "진행 중인 제품 작업"):
            self.database.reset_product_quality_baseline("P001")

    def test_consecutive_duplicate_does_not_add_records(self):
        first_event_id = self.send_state("running", 1)
        duplicate_event_id = self.send_state("running", 1)

        with self.database.connect() as connection:
            event_count = connection.execute(
                "SELECT COUNT(*) FROM worker_state_events"
            ).fetchone()[0]
            step_count = connection.execute(
                "SELECT COUNT(*) FROM step_runs"
            ).fetchone()[0]

        self.assertIsNotNone(first_event_id)
        self.assertIsNone(duplicate_event_id)
        self.assertEqual(event_count, 1)
        self.assertEqual(step_count, 1)

    def test_duplicate_complete_pass_does_not_create_another_product_run(self):
        self.send_state("running", 5)
        first_event_id = self.send_state("complete", 5, "pass")
        duplicate_event_id = self.send_state("complete", 5, "pass")

        with self.database.connect() as connection:
            product_run_count = connection.execute(
                "SELECT COUNT(*) FROM product_runs"
            ).fetchone()[0]
            judgement_count = connection.execute(
                "SELECT COUNT(*) FROM judgement_logs"
            ).fetchone()[0]
        self.assertIsNotNone(first_event_id)
        self.assertIsNone(duplicate_event_id)
        self.assertEqual(product_run_count, 1)
        self.assertEqual(judgement_count, 1)

    def test_complete_with_pass_counts_judgement_and_product_completion(self):
        self.send_state("running", 5)
        self.send_state("complete", 5, "pass")

        summary = self.database.get_product_step_quality_summary("P001")
        product = self.database.search_products("P001")[0]

        self.assertEqual(summary[4]["pass_count"], 1)
        self.assertEqual(summary[4]["fail_count"], 0)
        self.assertEqual(product["completed_count"], 1)
        self.assertEqual(product["defect_count"], 0)

    def test_step_transition_pass_is_attached_to_previous_step(self):
        self.send_state("running", 1)
        self.send_state("running", 2, event="step_pass")

        summary = self.database.get_product_step_quality_summary("P001")
        work_state = self.database.get_incomplete_work_state("1001")

        self.assertEqual(summary[0]["pass_count"], 1)
        self.assertEqual(summary[1]["pass_count"], 0)
        self.assertEqual(work_state["current_step"], 2)
        self.assertEqual(work_state["last_result"], "pass")

    def test_incomplete_work_state_is_returned_on_worker_login(self):
        self.send_state("running", 1)
        self.send_state("running", 2, event="step_pass")
        self.send_state("running", 2, "fail", event="ai_fail")
        self.send_state("paused", 2)

        gateway = MonitoringGatewayThread(self.database, host="127.0.0.1", port=0)
        response = gateway._process_request({
            "type": "auth", "employee_id": "1001", "password": "worker1234",
        })

        self.assertTrue(response["ok"])
        self.assertEqual(response["employee"]["employee_id"], "1001")
        self.assertEqual(response["work_state"], {
            "product_id": "P001",
            "product_name": "스마트 액추에이터 A",
            "total_steps": 5,
            "current_step": 2,
            "state": "paused",
            "last_result": "fail",
        })

    def test_completed_work_is_not_returned_on_worker_login(self):
        self.send_state("running", 5)
        self.send_state("complete", 5, "pass")

        gateway = MonitoringGatewayThread(self.database, host="127.0.0.1", port=0)
        response = gateway._process_request({
            "type": "auth", "employee_id": "1001", "password": "worker1234",
        })

        self.assertTrue(response["ok"])
        self.assertIsNone(response["work_state"])

    def test_worker_login_ip_routes_messages_until_logout(self):
        registry = WorkerEndpointRegistry()
        gateway = MonitoringGatewayThread(
            self.database, host="127.0.0.1", port=0,
            endpoint_registry=registry,
        )
        response = gateway._process_request({
            "type": "auth", "employee_id": "1001", "password": "worker1234",
        }, "10.10.15.51")
        token = response["token"]

        self.assertEqual(registry.resolve("1001"), "10.10.15.51")
        rejected = gateway._process_request({
            "type": "products", "token": token,
        }, "10.10.15.52")
        self.assertFalse(rejected["ok"])

        logout = gateway._process_request({
            "type": "logout", "token": token,
        }, "10.10.15.51")
        self.assertTrue(logout["ok"])
        self.assertIsNone(registry.resolve("1001"))

        client = TcpClient(endpoint_registry=registry)
        result = client.send_employee_message("1001", "확인")
        self.assertFalse(result.success)
        self.assertIn("로그인한 Jetson", result.message)

    def test_latest_login_replaces_same_employee_previous_token(self):
        registry = WorkerEndpointRegistry()
        gateway = MonitoringGatewayThread(
            self.database, host="127.0.0.1", port=0,
            endpoint_registry=registry,
        )
        first = gateway._process_request({
            "type": "auth", "employee_id": "1001", "password": "worker1234",
        }, "10.10.15.51")
        second = gateway._process_request({
            "type": "auth", "employee_id": "1001", "password": "worker1234",
        }, "10.10.15.52")

        self.assertEqual(registry.resolve("1001"), "10.10.15.52")
        stale = gateway._process_request({
            "type": "products", "token": first["token"],
        }, "10.10.15.51")
        current = gateway._process_request({
            "type": "products", "token": second["token"],
        }, "10.10.15.52")
        self.assertFalse(stale["ok"])
        self.assertTrue(current["ok"])

    def test_unknown_product_is_rejected_without_partial_event(self):
        with self.assertRaisesRegex(ValueError, "등록되지 않은 제품"):
            self.database.record_worker_state({
                "employee_id": "1001",
                "product_id": "UNKNOWN",
                "product_name": "없는 제품",
                "state": "running",
                "current_step": 1,
                "total_steps": 1,
                "last_result": "waiting",
            })

        with self.database.connect() as connection:
            event_count = connection.execute(
                "SELECT COUNT(*) FROM worker_state_events"
            ).fetchone()[0]
        self.assertEqual(event_count, 0)

    def test_revoked_worker_cannot_login_or_send_state_but_keeps_history(self):
        self.database.start_work_session("1001")
        self.send_state("idle", 0)

        revoked = self.database.revoke_worker("1001")

        self.assertEqual(revoked, {"employee_id": "1001", "name": "홍길동"})
        self.assertIsNone(self.database.verify_worker_login("1001", "worker1234"))
        self.assertNotIn(
            "1001", [employee["employee_id"] for employee in self.database.search_employees("")]
        )
        with self.assertRaisesRegex(ValueError, "사용할 수 없는 작업자 계정"):
            self.send_state("running", 1)
        with self.database.connect() as connection:
            logout_at = connection.execute(
                "SELECT logout_at FROM work_sessions WHERE employee_id = ?",
                ("1001",),
            ).fetchone()["logout_at"]
            event_count = connection.execute(
                "SELECT COUNT(*) FROM worker_state_events WHERE employee_id = ?",
                ("1001",),
            ).fetchone()[0]
        self.assertIsNotNone(logout_at)
        self.assertEqual(event_count, 1)

    def test_admin_account_cannot_be_revoked_as_worker(self):
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO employees(employee_id, name, password_hash, role)
                   VALUES (?, ?, ?, ?)""",
                ("admin", "관리자", self.database.hash_password("admin1234"), "admin"),
            )
        with self.assertRaisesRegex(ValueError, "작업자 계정만"):
            self.database.revoke_worker("admin")

    def test_new_event_uses_korea_standard_time(self):
        self.send_state("idle", 0)
        with self.database.connect() as connection:
            received_at = connection.execute(
                "SELECT received_at FROM worker_state_events"
            ).fetchone()[0]

        saved_time = datetime.fromisoformat(received_at)
        korea_now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)
        self.assertLess(abs((korea_now - saved_time).total_seconds()), 5)

    def test_legacy_utc_timestamps_are_migrated_only_once(self):
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM app_metadata WHERE key = 'timestamps_kst_v1'"
            )
            connection.execute(
                """INSERT INTO worker_state_events(
                       employee_id, product_id, product_name, state, current_step,
                       total_steps, last_result, received_at
                   ) VALUES ('1001', 'P001', '스마트 액추에이터 A', 'idle', 0,
                             5, 'waiting', '2026-09-01 07:00:00')"""
            )
            connection.execute(
                """INSERT INTO work_sessions(employee_id, login_at, logout_at)
                   VALUES ('1001', '2026-09-01 07:00:00', '2026-09-01 08:00:00')"""
            )
            product_run_id = connection.execute(
                """INSERT INTO product_runs(
                       employee_id, product_id, started_at, completed_at, result
                   ) VALUES ('1001', 'P001', '2026-09-01 07:00:00', NULL, 'in_progress')"""
            ).lastrowid
            step_run_id = connection.execute(
                """INSERT INTO step_runs(product_run_id, step_no, started_at, completed_at)
                   VALUES (?, 1, '2026-09-01 07:00:00', NULL)""",
                (product_run_id,),
            ).lastrowid
            connection.execute(
                """INSERT INTO judgement_logs(
                       step_run_id, result, judged_at
                   ) VALUES (?, 'fail', '2026-09-01 07:30:00')""",
                (step_run_id,),
            )

        self.database.initialize_database()
        self.database.initialize_database()
        with self.database.connect() as connection:
            received_at = connection.execute(
                "SELECT received_at FROM worker_state_events"
            ).fetchone()[0]
            session = connection.execute(
                "SELECT login_at, logout_at FROM work_sessions"
            ).fetchone()
            judged_at = connection.execute(
                "SELECT judged_at FROM judgement_logs"
            ).fetchone()["judged_at"]

        self.assertEqual(received_at, "2026-09-01 16:00:00")
        self.assertEqual(session["login_at"], "2026-09-01 16:00:00")
        self.assertEqual(session["logout_at"], "2026-09-01 17:00:00")
        self.assertEqual(judged_at, "2026-09-01 16:30:00")

    def test_quality_logs_keep_only_non_derived_relation_keys(self):
        self.send_state("running", 2, "fail")
        self.database.record_worker_state({
            "employee_id": "1001",
            "product_id": "P001",
            "product_name": "스마트 액추에이터 A",
            "state": "running",
            "current_step": 2,
            "total_steps": 5,
            "last_result": "defect",
            "event": "manual_defect",
            "defect_type": "manual",
        })

        with self.database.connect() as connection:
            judgement_columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(judgement_logs)"
                ).fetchall()
            }
            defect_columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(defect_logs)"
                ).fetchall()
            }

        self.assertEqual(
            judgement_columns,
            {"judgement_id", "step_run_id", "result", "source", "detail", "judged_at"},
        )
        self.assertEqual(
            defect_columns,
            {"defect_id", "step_run_id", "defect_type", "detail", "defect_at"},
        )
        self.assertEqual(
            self.database.get_product_step_quality_summary("P001")[1]["fail_count"], 1
        )
        self.assertEqual(self.database.get_defect_logs("1001")[0]["step_no"], 2)

    def test_legacy_quality_logs_are_normalized_without_losing_history(self):
        self.send_state("running", 2, "fail")
        self.database.record_worker_state({
            "employee_id": "1001",
            "product_id": "P001",
            "product_name": "스마트 액추에이터 A",
            "state": "running",
            "current_step": 2,
            "total_steps": 5,
            "last_result": "defect",
            "event": "manual_defect",
            "defect_type": "manual",
            "detail": "변환 보존 확인",
        })
        with self.database.connect() as connection:
            connection.executescript(
                """
                ALTER TABLE judgement_logs RENAME TO judgement_logs_normalized;
                CREATE TABLE judgement_logs (
                    judgement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_run_id INTEGER NOT NULL,
                    step_run_id INTEGER NOT NULL,
                    employee_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    step_no INTEGER NOT NULL,
                    result TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'inspection',
                    detail TEXT NOT NULL DEFAULT '',
                    judged_at DATETIME NOT NULL
                );
                INSERT INTO judgement_logs
                SELECT jl.judgement_id, sr.product_run_id, jl.step_run_id,
                       pr.employee_id, pr.product_id, sr.step_no, jl.result,
                       jl.source, jl.detail, jl.judged_at
                FROM judgement_logs_normalized AS jl
                JOIN step_runs AS sr ON sr.step_run_id = jl.step_run_id
                JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id;
                DROP TABLE judgement_logs_normalized;

                ALTER TABLE defect_logs RENAME TO defect_logs_normalized;
                CREATE TABLE defect_logs (
                    defect_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_run_id INTEGER NOT NULL UNIQUE,
                    employee_id TEXT NOT NULL,
                    product_id TEXT NOT NULL,
                    step_no INTEGER NOT NULL,
                    defect_type TEXT NOT NULL DEFAULT 'manual',
                    detail TEXT NOT NULL DEFAULT '',
                    defect_at DATETIME NOT NULL
                );
                INSERT INTO defect_logs
                SELECT dl.defect_id, sr.product_run_id, pr.employee_id,
                       pr.product_id, sr.step_no, dl.defect_type,
                       dl.detail, dl.defect_at
                FROM defect_logs_normalized AS dl
                JOIN step_runs AS sr ON sr.step_run_id = dl.step_run_id
                JOIN product_runs AS pr ON pr.product_run_id = sr.product_run_id;
                DROP TABLE defect_logs_normalized;
                """
            )

        self.database.initialize_database()
        with self.database.connect() as connection:
            judgement_columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(judgement_logs)"
                ).fetchall()
            }
            defect_columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(defect_logs)"
                ).fetchall()
            }
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM judgement_logs").fetchone()[0], 1
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM defect_logs").fetchone()[0], 1
            )

        self.assertNotIn("product_id", judgement_columns)
        self.assertNotIn("employee_id", defect_columns)
        summary = self.database.get_product_step_quality_summary("P001")
        self.assertEqual(summary[1]["fail_count"], 1)
        self.assertEqual(summary[1]["defect_button_count"], 1)


if __name__ == "__main__":
    unittest.main()
