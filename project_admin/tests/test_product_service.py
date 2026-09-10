"""ProductService의 CRUD 조합과 보상 정리를 검증합니다."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.product_service import ProductService


class FakeProductDatabase:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.guides: list[dict] = []
        self.product = {
            "product_id": "P001",
            "product_name": "샘플 제품",
            "total_steps": 2,
        }
        self.create_error: Exception | None = None

    def create_product(self, **kwargs) -> None:
        self.calls.append(("create_product", kwargs))
        if self.create_error:
            raise self.create_error

    def update_product(self, **kwargs) -> None:
        self.calls.append(("update_product", kwargs))

    def delete_product(self, product_id: str, cascade_history: bool = False) -> None:
        self.calls.append(("delete_product", product_id))

    def replace_product_step_guides(self, product_id: str, guides: list[dict]) -> None:
        self.calls.append(("replace_product_step_guides", product_id, guides))
        self.guides = guides

    def get_product(self, product_id: str) -> dict | None:
        self.calls.append(("get_product", product_id))
        return dict(self.product) if product_id == self.product["product_id"] else None

    def get_product_step_guides(self, product_id: str) -> list[dict]:
        self.calls.append(("get_product_step_guides", product_id))
        return list(self.guides)


class ProductServiceTests(unittest.TestCase):
    def test_create_image_failure_compensates_created_product_and_files(self) -> None:
        database = FakeProductDatabase()
        cleanup_calls: list[tuple[str, set[int]]] = []

        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "created.jpg"

            def save_image(product_id: str, step_no: int, source_path: str) -> dict:
                image_path.write_bytes(b"created by test")
                raise OSError("image write failed")

            def cleanup(product_id: str, active_steps: set[int]) -> None:
                cleanup_calls.append((product_id, active_steps))
                image_path.unlink(missing_ok=True)

            service = ProductService(
                database,
                save_image=save_image,
                delete_unused_images=cleanup,
            )

            with self.assertRaises(OSError):
                service.create({
                    "product_id": "P001",
                    "product_name": "제품",
                    "total_steps": 1,
                    "step_images": {1: "source.png"},
                })

            self.assertEqual(database.calls[0][0], "create_product")
            self.assertIn(("delete_product", "P001"), database.calls)
            self.assertEqual(cleanup_calls, [("P001", set())])
            self.assertFalse(image_path.exists())

    def test_create_integrity_error_does_not_delete_existing_product(self) -> None:
        database = FakeProductDatabase()
        database.create_error = sqlite3.IntegrityError("duplicate")
        service = ProductService(database)

        with self.assertRaises(sqlite3.IntegrityError):
            service.create({
                "product_id": "P001",
                "product_name": "중복 제품",
                "total_steps": 1,
            })

        self.assertEqual([call[0] for call in database.calls], ["create_product"])

    def test_create_update_delete_call_order_and_guides(self) -> None:
        database = FakeProductDatabase()
        service_calls: list[tuple] = []

        def save_image(product_id: str, step_no: int, source_path: str) -> dict:
            service_calls.append(("save_image", product_id, step_no, source_path))
            return {
                "step_no": step_no,
                "image_path": f"{product_id}/step_{step_no}.jpg",
                "mime_type": "image/jpeg",
                "byte_size": 10,
                "sha256": f"hash-{step_no}",
            }

        def cleanup(product_id: str, active_steps: set[int]) -> None:
            service_calls.append(("cleanup", product_id, active_steps))

        service = ProductService(
            database,
            save_image=save_image,
            delete_unused_images=cleanup,
        )
        service.create({
            "product_id": "P001",
            "product_name": "제품",
            "total_steps": 2,
            "step_images": {2: "two.png", 1: "one.png"},
        })
        service.update({
            "product_id": "P001",
            "product_name": "수정 제품",
            "total_steps": 2,
            "step_images": {1: "new-one.png"},
        })
        service.delete("P001")

        self.assertEqual(
            [call[0] for call in database.calls],
            [
                "create_product",
                "replace_product_step_guides",
                "update_product",
                "replace_product_step_guides",
                "delete_product",
            ],
        )
        self.assertEqual(
            service_calls,
            [
                ("save_image", "P001", 1, "one.png"),
                ("save_image", "P001", 2, "two.png"),
                ("cleanup", "P001", {1, 2}),
                ("save_image", "P001", 1, "new-one.png"),
                ("cleanup", "P001", {1}),
                ("cleanup", "P001", set()),
            ],
        )
        self.assertEqual(database.guides[0]["sha256"], "hash-1")

    def test_get_for_edit_includes_only_existing_image_paths(self) -> None:
        database = FakeProductDatabase()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "step_001.jpg"
            existing.write_bytes(b"image")
            missing = root / "step_002.jpg"
            database.guides = [
                {"step_no": 1, "image_path": "one.jpg"},
                {"step_no": 2, "image_path": "missing.jpg"},
            ]

            def resolve(path: str) -> Path:
                return existing if path == "one.jpg" else missing

            service = ProductService(database, resolve_image_path=resolve)
            product = service.get_for_edit("P001")

            self.assertIsNotNone(product)
            self.assertEqual(product["step_images"], {1: str(existing)})


if __name__ == "__main__":
    unittest.main()
