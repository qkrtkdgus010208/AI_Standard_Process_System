import base64
import sqlite3
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage

from database_manager import DatabaseManager
from monitoring_gateway import MonitoringGatewayThread
from tcp_client import TcpClient, WorkerEndpointRegistry
import config
from step_guide_storage import resolve_guide_path, save_guide_image


class WorkerStatePersistenceTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self._original_guide_dir = config.STEP_GUIDE_IMAGE_DIR
        config.STEP_GUIDE_IMAGE_DIR = Path(self.temporary_directory.name) / "step_guides"
        self.database = DatabaseManager(
            Path(self.temporary_directory.name) / "test_factory.db"
        )
        self.database.initialize_database()
        self.database.create_worker("1001", "홍길동", "worker1234")
        self.database.create_product("P001", "스마트 액추에이터 A", 5)

    def tearDown(self):
        config.STEP_GUIDE_IMAGE_DIR = self._original_guide_dir
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
        self.assertEqual(pauses[0]["product_id"], "P001")
        self.assertEqual(pauses[0]["step_no"], 1)

        emp_pauses = self.database.get_employee_pause_logs("1001")
        self.assertEqual(len(emp_pauses), 1)
        self.assertEqual(emp_pauses[0]["product_id"], "P001")
        self.assertEqual(emp_pauses[0]["product_name"], "스마트 액추에이터 A")
        self.assertEqual(emp_pauses[0]["step_no"], 1)
        self.assertEqual(emp_pauses[0]["pause_seconds"], 75)

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

    def test_step_guide_metadata_is_replaced_and_trimmed_with_product_steps(self):
        self.database.replace_product_step_guides("P001", [
            {
                "step_no": 1, "image_path": "p001/step_001.jpg",
                "mime_type": "image/jpeg", "byte_size": 3, "sha256": "abc",
            },
            {
                "step_no": 5, "image_path": "p001/step_005.jpg",
                "mime_type": "image/jpeg", "byte_size": 3, "sha256": "def",
            },
        ])
        self.assertEqual(
            [row["step_no"] for row in self.database.get_product_step_guides("P001")],
            [1, 5],
        )

        self.database.update_product("P001", "스마트 액추에이터 A", 3)

        guides = self.database.get_product_step_guides("P001")
        self.assertEqual([row["step_no"] for row in guides], [1])

    def test_step_guide_image_is_normalized_into_managed_storage(self):
        source = Path(self.temporary_directory.name) / "source.png"
        image = QImage(1600, 900, QImage.Format_RGB32)
        image.fill(Qt.red)
        self.assertTrue(image.save(str(source), "PNG"))

        guide = save_guide_image("P001", 1, str(source))
        stored_path = resolve_guide_path(guide["image_path"])
        stored = QImage(str(stored_path))

        self.assertTrue(stored_path.is_file())
        self.assertEqual(guide["mime_type"], "image/jpeg")
        self.assertLessEqual(stored.width(), 1280)
        self.assertLessEqual(stored.height(), 720)
        self.assertEqual(guide["byte_size"], stored_path.stat().st_size)

    def test_gateway_returns_current_step_guide_image(self):
        image_bytes = b"test-image-bytes"
        image_path = config.STEP_GUIDE_IMAGE_DIR / "p001" / "step_002.jpg"
        image_path.parent.mkdir(parents=True)
        image_path.write_bytes(image_bytes)
        self.database.replace_product_step_guides("P001", [{
            "step_no": 2,
            "image_path": "p001/step_002.jpg",
            "mime_type": "image/jpeg",
            "byte_size": len(image_bytes),
            "sha256": "guide-hash",
        }])
        gateway = MonitoringGatewayThread(self.database, host="127.0.0.1", port=0)
        login = gateway._process_request({
            "type": "auth", "employee_id": "1001", "password": "worker1234",
        })

        response = gateway._process_request({
            "type": "step_guide", "token": login["token"],
            "product_id": "P001", "step_no": 2,
        })

        self.assertTrue(response["ok"])
        self.assertEqual(response["guide"]["step_no"], 2)
        self.assertEqual(
            base64.b64decode(response["guide"]["image_base64"]), image_bytes
        )

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

    def test_stale_logout_cannot_close_current_work_session(self):
        gateway = MonitoringGatewayThread(self.database, host="127.0.0.1", port=0)
        first = gateway._process_request({
            "type": "auth", "employee_id": "1001", "password": "worker1234",
        }, "10.10.15.51")
        second = gateway._process_request({
            "type": "auth", "employee_id": "1001", "password": "worker1234",
        }, "10.10.15.52")

        stale_logout = gateway._process_request({
            "type": "logout", "token": first["token"],
        }, "10.10.15.51")

        self.assertFalse(stale_logout["ok"])
        self.assertTrue(gateway._process_request({
            "type": "products", "token": second["token"],
        }, "10.10.15.52")["ok"])
        with self.database.connect() as connection:
            session = connection.execute(
                """SELECT logout_at FROM work_sessions
                   WHERE employee_id = ? AND logout_at IS NULL""",
                ("1001",),
            ).fetchone()
        self.assertIsNotNone(session)

    def test_state_rechecks_token_after_previous_login_is_displaced(self):
        gateway = MonitoringGatewayThread(self.database, host="127.0.0.1", port=0)
        first = gateway._process_request({
            "type": "auth", "employee_id": "1001", "password": "worker1234",
        }, "10.10.15.51")
        gateway._process_request({
            "type": "auth", "employee_id": "1001", "password": "worker1234",
        }, "10.10.15.52")

        stale_state = gateway._process_request({
            "type": "state", "token": first["token"],
            "product_id": "P001", "product_name": "스마트 액추에이터 A",
            "state": "running", "current_step": 1, "total_steps": 5,
        }, "10.10.15.51")

        self.assertFalse(stale_state["ok"])
        with self.database.connect() as connection:
            event_count = connection.execute(
                "SELECT COUNT(*) FROM worker_state_events"
            ).fetchone()[0]
        self.assertEqual(event_count, 0)

    def test_same_employee_state_writes_are_serialized(self):
        gateway = MonitoringGatewayThread(self.database, host="127.0.0.1", port=0)
        login = gateway._process_request({
            "type": "auth", "employee_id": "1001", "password": "worker1234",
        }, "10.10.15.51")
        active = 0
        maximum = 0
        counter_lock = threading.Lock()
        original_record = self.database.record_worker_state

        def tracked_record(state):
            nonlocal active, maximum
            with counter_lock:
                active += 1
                maximum = max(maximum, active)
            try:
                time.sleep(0.03)
                return original_record(state)
            finally:
                with counter_lock:
                    active -= 1

        self.database.record_worker_state = tracked_record
        requests = [
            {
                "type": "state", "token": login["token"],
                "product_id": "P001", "product_name": "스마트 액추에이터 A",
                "state": "running", "current_step": step, "total_steps": 5,
            }
            for step in (1, 2)
        ]
        results = []
        threads = [threading.Thread(
            target=lambda request=request: results.append(
                gateway._process_request(request, "10.10.15.51")
            )
        ) for request in requests]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(maximum, 1)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result["ok"] for result in results))

    def test_concurrent_database_state_writes_do_not_duplicate_event(self):
        state = {
            "employee_id": "1001",
            "name": "홍길동",
            "product_id": "P001",
            "product_name": "스마트 액추에이터 A",
            "state": "running",
            "current_step": 1,
            "total_steps": 5,
            "last_result": "waiting",
            "event": "",
            "defect_type": "",
            "detail": "",
        }
        start = threading.Barrier(3)
        results = []
        errors = []

        def record_state():
            start.wait()
            try:
                results.append(self.database.record_worker_state(state))
            except Exception as error:
                errors.append(error)

        threads = [threading.Thread(target=record_state) for _ in range(2)]
        for thread in threads:
            thread.start()
        start.wait()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(sum(result is not None for result in results), 1)
        with self.database.connect() as connection:
            event_count = connection.execute(
                "SELECT COUNT(*) FROM worker_state_events"
            ).fetchone()[0]
        self.assertEqual(event_count, 1)

    def test_gateway_event_id_makes_fail_retry_idempotent(self):
        gateway = MonitoringGatewayThread(self.database, host="127.0.0.1", port=0)
        login = gateway._process_request({
            "type": "auth", "employee_id": "1001", "password": "worker1234",
        }, "10.10.15.51")
        request = {
            "type": "state",
            "token": login["token"],
            "event_id": "11111111-1111-4111-8111-111111111111",
            "product_id": "P001",
            "product_name": "스마트 액추에이터 A",
            "state": "running",
            "current_step": 1,
            "total_steps": 5,
            "last_result": "fail",
            "event": "ai_fail",
        }

        self.assertTrue(gateway._process_request(request, "10.10.15.51")["ok"])
        self.assertTrue(gateway._process_request(request, "10.10.15.51")["ok"])

        with self.database.connect() as connection:
            event_count = connection.execute(
                "SELECT COUNT(*) FROM worker_state_events WHERE client_event_id = ?",
                (request["event_id"],),
            ).fetchone()[0]
            judgement_count = connection.execute(
                "SELECT COUNT(*) FROM judgement_logs WHERE result = 'fail'"
            ).fetchone()[0]
        self.assertEqual(event_count, 1)
        self.assertEqual(judgement_count, 1)

    def test_different_event_ids_keep_separate_real_failures(self):
        base = {
            "employee_id": "1001",
            "product_id": "P001",
            "product_name": "스마트 액추에이터 A",
            "state": "running",
            "current_step": 1,
            "total_steps": 5,
            "last_result": "fail",
            "event": "ai_fail",
        }
        self.database.record_worker_state({
            **base, "client_event_id": "22222222-2222-4222-8222-222222222222",
        })
        self.database.record_worker_state({
            **base, "client_event_id": "33333333-3333-4333-8333-333333333333",
        })

        with self.database.connect() as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM worker_state_events"
            ).fetchone()[0], 2)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM judgement_logs WHERE result = 'fail'"
            ).fetchone()[0], 2)

    def test_event_id_retry_after_another_event_is_still_ignored(self):
        first = {
            "employee_id": "1001",
            "product_id": "P001",
            "product_name": "스마트 액추에이터 A",
            "state": "running",
            "current_step": 1,
            "total_steps": 5,
            "last_result": "fail",
            "event": "ai_fail",
            "client_event_id": "66666666-6666-4666-8666-666666666666",
        }
        second = {
            **first,
            "current_step": 2,
            "last_result": "waiting",
            "event": "step_pass",
            "client_event_id": "77777777-7777-4777-8777-777777777777",
        }
        self.database.record_worker_state(first)
        self.database.record_worker_state(second)

        self.assertIsNone(self.database.record_worker_state(first))
        with self.database.connect() as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM worker_state_events"
            ).fetchone()[0], 2)

    def test_same_event_id_is_independent_for_each_employee(self):
        self.database.create_worker("1002", "김작업", "worker5678")
        event_id = "88888888-8888-4888-8888-888888888888"
        base = {
            "product_id": "P001",
            "product_name": "스마트 액추에이터 A",
            "state": "running",
            "current_step": 1,
            "total_steps": 5,
            "last_result": "waiting",
            "client_event_id": event_id,
        }
        self.database.record_worker_state({**base, "employee_id": "1001"})
        self.database.record_worker_state({**base, "employee_id": "1002"})

        with self.database.connect() as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM worker_state_events WHERE client_event_id = ?",
                (event_id,),
            ).fetchone()[0], 2)

    def test_concurrent_same_event_id_is_processed_once(self):
        state = {
            "employee_id": "1001",
            "product_id": "P001",
            "product_name": "스마트 액추에이터 A",
            "state": "running",
            "current_step": 1,
            "total_steps": 5,
            "last_result": "fail",
            "event": "ai_fail",
            "client_event_id": "99999999-9999-4999-8999-999999999999",
        }
        start = threading.Barrier(3)
        results = []
        errors = []

        def record_state():
            start.wait()
            try:
                results.append(self.database.record_worker_state(state))
            except Exception as error:
                errors.append(error)

        threads = [threading.Thread(target=record_state) for _ in range(2)]
        for thread in threads:
            thread.start()
        start.wait()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(sum(result is not None for result in results), 1)
        with self.database.connect() as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM judgement_logs WHERE result = 'fail'"
            ).fetchone()[0], 1)

    def test_reused_event_id_with_different_payload_is_rejected(self):
        base = {
            "employee_id": "1001",
            "product_id": "P001",
            "product_name": "스마트 액추에이터 A",
            "state": "running",
            "current_step": 1,
            "total_steps": 5,
            "last_result": "fail",
            "event": "ai_fail",
            "client_event_id": "44444444-4444-4444-8444-444444444444",
        }
        self.database.record_worker_state(base)

        with self.assertRaisesRegex(ValueError, "같은 event_id"):
            self.database.record_worker_state({**base, "detail": "다른 검사 결과"})

        with self.database.connect() as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM worker_state_events"
            ).fetchone()[0], 1)
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM judgement_logs"
            ).fetchone()[0], 1)

    def test_complete_event_retry_does_not_increase_production_count(self):
        complete = {
            "employee_id": "1001",
            "product_id": "P001",
            "product_name": "스마트 액추에이터 A",
            "state": "complete",
            "current_step": 5,
            "total_steps": 5,
            "last_result": "pass",
            "event": "complete",
            "client_event_id": "55555555-5555-4555-8555-555555555555",
        }
        first = self.database.record_worker_state(complete)
        retry = self.database.record_worker_state(complete)

        self.assertIsNotNone(first)
        self.assertIsNone(retry)
        with self.database.connect() as connection:
            self.assertEqual(connection.execute(
                "SELECT COUNT(*) FROM product_runs WHERE result = 'pass'"
            ).fetchone()[0], 1)

    def test_invalid_event_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "UUID"):
            self.database.record_worker_state({
                "employee_id": "1001",
                "product_id": "P001",
                "product_name": "스마트 액추에이터 A",
                "state": "running",
                "current_step": 1,
                "total_steps": 5,
                "last_result": "waiting",
                "client_event_id": "not-a-uuid",
            })

    def test_legacy_database_adds_client_event_id_without_losing_events(self):
        legacy_path = Path(self.temporary_directory.name) / "legacy_event_id.db"
        connection = sqlite3.connect(legacy_path)
        connection.execute(
            """CREATE TABLE worker_state_events (
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
                   received_at DATETIME NOT NULL
               )"""
        )
        connection.execute(
            """INSERT INTO worker_state_events(
                   employee_id, product_id, product_name, state, current_step,
                   total_steps, last_result, received_at
               ) VALUES ('1001', 'P001', '기존 제품', 'idle', 0, 5, 'waiting',
                         '2026-09-08 09:00:00')"""
        )
        connection.commit()
        connection.close()

        legacy_database = DatabaseManager(legacy_path)
        legacy_database.initialize_database()
        with legacy_database.connect() as connection:
            columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(worker_state_events)"
                ).fetchall()
            }
            existing = connection.execute(
                "SELECT client_event_id FROM worker_state_events"
            ).fetchone()

        self.assertIn("client_event_id", columns)
        self.assertIsNone(existing["client_event_id"])

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
