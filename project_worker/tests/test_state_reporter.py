import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.state_reporter import MonitoringEventThread


class MonitoringEventThreadTest(unittest.TestCase):
    def setUp(self):
        self.reporter = MonitoringEventThread(SimpleNamespace(
            token="test-token",
            is_test_session=True,
        ))

    def test_enqueue_assigns_one_event_id_and_copies_state(self):
        state = {
            "product_id": "P001",
            "product_name": "제품 A",
            "state": "running",
            "current_step": 1,
            "total_steps": 5,
            "last_result": "fail",
            "event": "ai_fail",
        }
        event_id = "11111111-1111-4111-8111-111111111111"
        with patch("services.state_reporter.uuid.uuid4", return_value=event_id):
            self.reporter.enqueue_state(state)
        state["last_result"] = "waiting"

        payload = self.reporter._queue.get_nowait()
        self.assertEqual(payload["event_id"], event_id)
        self.assertEqual(payload["last_result"], "fail")

    def test_each_logical_enqueue_gets_a_different_event_id(self):
        state = {
            "product_id": "P001",
            "state": "running",
            "current_step": 1,
            "total_steps": 5,
        }
        event_ids = [
            "22222222-2222-4222-8222-222222222222",
            "33333333-3333-4333-8333-333333333333",
        ]
        with patch("services.state_reporter.uuid.uuid4", side_effect=event_ids):
            self.reporter.enqueue_state(state)
            self.reporter.enqueue_state(state)

        first = self.reporter._queue.get_nowait()
        second = self.reporter._queue.get_nowait()
        self.assertEqual(first["event_id"], event_ids[0])
        self.assertEqual(second["event_id"], event_ids[1])


if __name__ == "__main__":
    unittest.main()
