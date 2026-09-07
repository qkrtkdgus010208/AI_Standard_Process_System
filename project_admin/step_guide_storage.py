"""제품 STEP별 기준 이미지 파일 저장과 검증을 담당합니다."""

from __future__ import annotations

import hashlib
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPainter

import config


def _product_directory(product_id: str) -> Path:
    key = hashlib.sha256(product_id.encode("utf-8")).hexdigest()[:24]
    return config.STEP_GUIDE_IMAGE_DIR / key


def resolve_guide_path(image_path: str) -> Path:
    """DB에 저장된 상대 경로를 안전한 절대 경로로 변환합니다."""
    root = config.STEP_GUIDE_IMAGE_DIR.resolve()
    candidate = (root / image_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("허용되지 않은 기준 이미지 경로입니다.")
    return candidate


def save_guide_image(product_id: str, step_no: int, source_path: str) -> dict:
    """선택 이미지를 1280×720 이내 JPEG로 정규화하여 저장합니다."""
    source = Path(source_path).resolve()
    if not source.is_file():
        raise ValueError(f"STEP {step_no} 이미지 파일을 찾을 수 없습니다.")
    if source.stat().st_size > config.STEP_GUIDE_MAX_SOURCE_BYTES:
        raise ValueError("기준 이미지 원본은 10MB 이하만 등록할 수 있습니다.")

    image = QImage(str(source))
    if image.isNull():
        raise ValueError(f"STEP {step_no} 파일은 지원되는 이미지가 아닙니다.")
    scaled = image.scaled(1280, 720, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    canvas = QImage(scaled.size(), QImage.Format_RGB888)
    canvas.fill(Qt.white)
    painter = QPainter(canvas)
    painter.drawImage(0, 0, scaled)
    painter.end()

    product_dir = _product_directory(product_id)
    product_dir.mkdir(parents=True, exist_ok=True)
    destination = product_dir / f"step_{int(step_no):03d}.jpg"
    if not canvas.save(str(destination), "JPEG", 88):
        raise OSError(f"STEP {step_no} 기준 이미지를 저장하지 못했습니다.")
    data = destination.read_bytes()
    if len(data) > config.STEP_GUIDE_MAX_RESPONSE_BYTES:
        destination.unlink(missing_ok=True)
        raise ValueError("변환된 기준 이미지 용량이 3MB를 초과합니다.")
    return {
        "step_no": int(step_no),
        "image_path": destination.relative_to(config.STEP_GUIDE_IMAGE_DIR).as_posix(),
        "mime_type": "image/jpeg",
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def delete_unused_guide_files(product_id: str, active_steps: set[int]) -> None:
    """DB에서 제거된 STEP의 관리 이미지 파일을 정리합니다."""
    product_dir = _product_directory(product_id)
    if not product_dir.exists():
        return
    for path in product_dir.glob("step_*.jpg"):
        try:
            step_no = int(path.stem.split("_")[-1])
        except ValueError:
            continue
        if step_no not in active_steps:
            path.unlink(missing_ok=True)
    if product_dir.exists() and not any(product_dir.iterdir()):
        product_dir.rmdir()
