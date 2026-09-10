"""제품 목록 조회 및 파싱을 담당하는 서비스 모듈입니다.

Monitoring PC SQLite DB의 products 테이블에서 제품 정보를 비동기로 조회하고
다양한 응답 형식을 ProductInfo 표준 객체로 변환합니다.
"""

import base64

from dataclasses import dataclass
from typing import Optional, Union

from PyQt5.QtCore import QThread, pyqtSignal

import config
from network.network_client import send_json_request
from services.state_reporter import _extract_int


@dataclass(frozen=True)
class ProductInfo:
    """모니터링 PC SQLite DB products 테이블에서 조회한 제품 정보입니다."""

    product_id: str
    product_name: str
    total_steps: int


def parse_product_item(item: Union[dict, list, tuple]) -> Optional[ProductInfo]:
    """모니터링 PC 응답 아이템을 ProductInfo로 변환합니다."""
    if isinstance(item, dict):
        pid = str(
            item.get("product_id") or item.get("id")
            or item.get("code") or item.get("product_code") or ""
        ).strip()
        pname = str(
            item.get("product_name") or item.get("name")
            or item.get("title") or item.get("item_name") or ""
        ).strip()
        if not pid or not pname:
            return None
        total_steps = _extract_int(
            item, ("total_steps", "steps", "total_step", "step_count", "process_count")
        ) or 1
        return ProductInfo(product_id=pid, product_name=pname, total_steps=max(1, total_steps))

    if isinstance(item, (list, tuple)) and len(item) >= 2:
        pid, pname = str(item[0]).strip(), str(item[1]).strip()
        if not pid or not pname:
            return None
        total_steps = 1
        if len(item) > 2:
            try:
                total_steps = int(item[2])
            except (ValueError, TypeError):
                pass
        return ProductInfo(product_id=pid, product_name=pname, total_steps=max(1, total_steps))

    return None


def fetch_products_from_monitoring_pc(token: str = "") -> list[ProductInfo]:
    """모니터링 PC Gateway에 요청하여 products 테이블의 제품 목록을 조회합니다."""
    last_error: Optional[str] = None

    for req_type in ("products", "get_products"):
        try:
            payload = {"type": req_type}
            if token:
                payload["token"] = token
            response = send_json_request(payload)
            if not isinstance(response, dict):
                continue
            if response.get("ok") is False:
                last_error = response.get("message", "요청 실패")
                continue
            raw_list = (
                response.get("products") or response.get("data")
                or response.get("items") or response.get("product_list") or []
            )
            if isinstance(raw_list, list):
                return [p for p in (parse_product_item(i) for i in raw_list) if p is not None]
        except (OSError, ConnectionError, ValueError) as err:
            last_error = f"네트워크 오류: {err}"
            break

    if last_error:
        raise ConnectionError(last_error)
    return []


def fetch_step_guide_from_monitoring_pc(token: str, product_id: str,
                                        step_no: int) -> Optional[bytes]:
    """현재 제품·STEP의 기준 이미지 한 장을 조회합니다."""
    response = send_json_request({
        "type": "step_guide", "token": token,
        "product_id": product_id, "step_no": int(step_no),
    })
    if not isinstance(response, dict) or response.get("ok") is False:
        message = response.get("message", "요청 실패") if isinstance(response, dict) else "응답 오류"
        raise ConnectionError(message)
    guide = response.get("guide")
    if not guide:
        return None
    encoded = str(guide.get("image_base64") or "")
    if not encoded:
        return None
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError("기준 이미지 데이터가 손상되었습니다.") from error


class ProductFetchThread(QThread):
    """모니터링 PC의 products 테이블에서 제품 목록을 비동기 조회하는 Thread입니다."""

    products_fetched = pyqtSignal(list, bool, str)

    def __init__(self, token: str = "", parent=None):
        super().__init__(parent)
        self.token = token
        self.finished.connect(self.deleteLater)

    def run(self) -> None:
        """모니터링 PC에 제품 목록을 요청하여 UI에 전달합니다."""
        if config.TEST_MODE:
            fallback = [
                ProductInfo(p["product_id"], p["product_name"], int(p["total_steps"]))
                for p in config.DEFAULT_PRODUCTS
            ]
            self.products_fetched.emit(fallback, True, f"TEST MODE 제품 {len(fallback)}건 로드 완료")
            return
        try:
            products = fetch_products_from_monitoring_pc(self.token)
            if products:
                self.products_fetched.emit(
                    products, True, f"모니터링 PC에서 제품 {len(products)}건 로드 완료"
                )
            else:
                self.products_fetched.emit(
                    [], False, "모니터링 PC의 products 테이블에 등록된 제품이 없습니다."
                )
        except Exception as error:
            self.products_fetched.emit([], False, f"모니터링 PC 제품 조회 실패: {error}")


class StepGuideFetchThread(QThread):
    """STEP 기준 이미지를 UI를 막지 않고 조회합니다."""

    guide_fetched = pyqtSignal(str, int, object, bool, str)

    def __init__(self, token: str, product_id: str, step_no: int, parent=None):
        super().__init__(parent)
        self.token = token
        self.product_id = product_id
        self.step_no = int(step_no)
        self.finished.connect(self.deleteLater)

    def run(self) -> None:
        try:
            image_data = fetch_step_guide_from_monitoring_pc(
                self.token, self.product_id, self.step_no
            )
            message = "기준 이미지 없음" if image_data is None else "기준 이미지 로드 완료"
            self.guide_fetched.emit(
                self.product_id, self.step_no, image_data, True, message
            )
        except Exception as error:
            self.guide_fetched.emit(
                self.product_id, self.step_no, None, False,
                f"STEP 기준 이미지 조회 실패: {error}",
            )
