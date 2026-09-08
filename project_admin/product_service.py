"""제품 CRUD와 STEP 기준 이미지 저장을 조합하는 서비스 계층입니다."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from database_manager import DatabaseManager
from step_guide_storage import (
    delete_unused_guide_files,
    resolve_guide_path,
    save_guide_image,
)


class ProductService:
    """제품 데이터와 기준 이미지의 변경 절차를 한 곳에서 관리합니다."""

    def __init__(
        self,
        database_manager: DatabaseManager,
        *,
        save_image: Callable[[str, int, str], dict[str, Any]] = save_guide_image,
        delete_unused_images: Callable[[str, set[int]], None] = delete_unused_guide_files,
        resolve_image_path: Callable[[str], Any] = resolve_guide_path,
    ) -> None:
        self.database_manager = database_manager
        self._save_image = save_image
        self._delete_unused_images = delete_unused_images
        self._resolve_image_path = resolve_image_path

    def create(self, data: dict[str, Any]) -> None:
        """제품과 선택된 STEP 이미지를 등록합니다."""
        product_id = str(data["product_id"])
        product_created = False
        try:
            self.database_manager.create_product(
                product_id=product_id,
                product_name=data["product_name"],
                total_steps=data["total_steps"],
            )
            product_created = True
            self._replace_step_images(product_id, data.get("step_images") or {})
        except Exception:
            if product_created:
                try:
                    self.database_manager.delete_product(product_id)
                    self._delete_unused_images(product_id, set())
                except Exception:
                    pass
            raise

    def update(self, data: dict[str, Any]) -> None:
        """제품 기본정보와 STEP 기준 이미지를 수정합니다."""
        product_id = str(data["product_id"])
        self.database_manager.update_product(
            product_id=product_id,
            product_name=data["product_name"],
            total_steps=data["total_steps"],
        )
        self._replace_step_images(product_id, data.get("step_images") or {})

    def delete(self, product_id: str) -> None:
        """제품과 연결된 기준 이미지 메타데이터 및 파일을 삭제합니다."""
        self.database_manager.delete_product(product_id)
        self._delete_unused_images(product_id, set())

    def get_for_edit(self, product_id: str) -> dict[str, Any] | None:
        """제품 기본정보와 존재하는 STEP 이미지 경로를 Dialog 형식으로 반환합니다."""
        product = self.database_manager.get_product(product_id)
        if product is None:
            return None
        guides = self.database_manager.get_product_step_guides(product_id)
        step_images: dict[int, str] = {}
        for guide in guides:
            path = self._resolve_image_path(guide["image_path"])
            if path.is_file():
                step_images[int(guide["step_no"])] = str(path)
        product["step_images"] = step_images
        return product

    def _replace_step_images(self, product_id: str, step_images: dict[int, str]) -> None:
        guides = [
            self._save_image(product_id, step_no, source_path)
            for step_no, source_path in sorted(step_images.items())
        ]
        self.database_manager.replace_product_step_guides(product_id, guides)
        self._delete_unused_images(product_id, {guide["step_no"] for guide in guides})
