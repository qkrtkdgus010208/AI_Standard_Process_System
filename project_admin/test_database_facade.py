import tempfile
import unittest
from pathlib import Path

from database_manager import DatabaseManager


class DatabaseFacadeTest(unittest.TestCase):
    def test_sample_data_is_complete_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = DatabaseManager(Path(temporary_directory) / "sample.db")
            database.initialize_database()
            database.insert_sample_data()
            database.insert_sample_data()

            with database.connect() as connection:
                counts = {
                    table: connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                    for table in (
                        "employees",
                        "products",
                        "work_sessions",
                        "product_runs",
                        "step_runs",
                        "pause_logs",
                    )
                }

        self.assertEqual(counts, {
            "employees": 2,
            "products": 1,
            "work_sessions": 1,
            "product_runs": 1,
            "step_runs": 2,
            "pause_logs": 1,
        })

    def test_format_seconds_compatibility_entry_point_is_preserved(self):
        self.assertEqual(DatabaseManager.format_seconds(3661), "01:01:01")


if __name__ == "__main__":
    unittest.main()
