"""AI Framework와 PyQt UI 사이의 의존성을 분리하는 판정 모듈입니다.

TensorRT 엔진(yolo26n_fp16.engine)과 recipe.json에 기반하여
실시간 프레임의 조립 정합성을 검증하고, 판정 결과와 함께
검출 바운딩 박스가 시각화된 프레임 및 상세 판정 사유를 생성합니다.
"""

import json
import os
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

import config

try:
    import cv2
except ImportError:
    cv2 = None

from ai.detector import Detector
from ai.normalizer import get_relative_center
from ai.inspector import (
    find_by_class,
    find_all_by_class,
    check_relative_position,
    match_multiple_positions,
)


@dataclass
class JudgeResult:
    """AI Backend 종류와 무관하게 UI에 전달되는 표준 판정 결과입니다."""

    result: str  # "PASS" 또는 "FAIL"
    confidence: float
    detail: str = ""
    reasons: list = field(default_factory=list)
    annotated_frame: Optional[object] = None
    step_no: int = 1


class BaseJudge:
    """판정 구현체가 따라야 할 인터페이스입니다."""

    def predict(
        self,
        frame,
        step_no: int = 1,
        product_name: str = "",
        product_id: str = "",
    ) -> JudgeResult:
        raise NotImplementedError

    def set_product(self, product_name: str = "", product_id: str = "") -> str:
        return ""


class MockJudge(BaseJudge):
    """장비와 모델 없이 PASS/FAIL 흐름을 시험하는 Mock 판정기입니다."""

    def predict(
        self,
        frame,
        step_no: int = 1,
        product_name: str = "",
        product_id: str = "",
    ) -> JudgeResult:
        time.sleep(0.18)
        is_pass = random.random() >= 0.25
        confidence = random.uniform(0.88, 0.99)
        result = "PASS" if is_pass else "FAIL"
        reasons = (
            ["Mock 조립 검사 정상 통과"]
            if is_pass
            else ["Mock 검사: 기준 부품 위치 오차 초과"]
        )
        return JudgeResult(
            result,
            confidence,
            f"Mock AI 판정: {result}",
            reasons=reasons,
            annotated_frame=frame,
            step_no=step_no,
        )

    def set_product(self, product_name: str = "", product_id: str = "") -> str:
        return "mock.json"


def resolve_recipe_path(ai_dir: Path, product_name: str = "", product_id: str = "") -> Path:
    """선택된 제품명 또는 제품 ID를 분석하여 적절한 .json 레시피 파일을 찾아 반환합니다."""
    name_clean = (product_name or "").strip().lower().replace(" ", "_")
    id_clean = (product_id or "").strip().lower().replace(" ", "_")
    parts = [p for p in (name_clean, id_clean) if p]
    combined = "_".join(parts)

    # 1. 픽업트럭 계열 키워드
    if any(kw in combined for kw in ("pickup", "truck", "픽업", "트럭")):
        truck_file = ai_dir / "pickup_truck.json"
        if truck_file.exists():
            return truck_file

    # 2. 레이싱카 계열 키워드
    if any(kw in combined for kw in ("racing", "car", "레이싱", "카", "레이서")):
        car_file = ai_dir / "racing_car.json"
        if car_file.exists():
            return car_file

    # 3. 제품 ID 또는 제품명과 직접 일치하는 파일명 (예: P001.json, pickup_truck.json 등)
    for key in parts:
        direct = ai_dir / f"{key}.json"
        if direct.exists():
            return direct

    # 4. ai_dir 내의 .json 파일 중 제품명/ID에 파일명(stem)이 포함된 경우 탐색
    if parts:
        for json_file in ai_dir.glob("*.json"):
            stem = json_file.stem.lower()
            if stem and any(stem in p or (len(p) >= 3 and p in stem) for p in parts):
                return json_file

    # 5. 기본 fallback: racing_car.json -> pickup_truck.json -> recipe.json
    for fallback_name in ("racing_car.json", "pickup_truck.json", "recipe.json"):
        fallback = ai_dir / fallback_name
        if fallback.exists():
            return fallback

    return ai_dir / "racing_car.json"


def _draw_box_label(frame, text: str, bx1: int, by1: int, color: tuple) -> None:
    """바운딩 박스 라벨을 프레임 가장자리에 잘리지 않도록 안전 여백(최소 x=60)을 두고 배경 상자와 함께 표시합니다."""
    if cv2 is None or frame is None:
        return
    fh, fw = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.55
    thickness = 2
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    tx = max(60, min(fw - tw - 20, bx1))
    ty = max(th + 20, min(fh - 20, by1 - 8))
    cv2.rectangle(
        frame,
        (tx - 4, ty - th - 4),
        (tx + tw + 4, ty + baseline + 2),
        (0, 0, 0),
        -1,
    )
    cv2.putText(frame, text, (tx, ty), font, scale, color, thickness)


class TensorRTJudge(BaseJudge):
    """YOLO TensorRT 엔진 및 제품별 레시피(.json) 기반 실제 조립 공정 정밀 검사 판정기입니다."""

    def __init__(self, engine_path: Optional[str] = None, recipe_path: Optional[str] = None):
        self.ai_dir = Path(__file__).resolve().parent.parent / "ai"

        v2_engine = self.ai_dir / "yolo26n_v2_fp16.engine"
        default_engine = self.ai_dir / "yolo26n_fp16.engine"
        test_engine = self.ai_dir / "yolo26n_fp16.engine.test"
        v2_onnx = self.ai_dir / "yolo26n_v2.onnx"
        onnx_path = self.ai_dir / "yolo26n.onnx"

        # 사용 가능한 모델 파일 탐색 (yolo26n_v2_fp16.engine 최우선)
        if engine_path:
            chosen_model = Path(engine_path)
        elif v2_engine.exists() and v2_engine.stat().st_size > 50000:
            chosen_model = v2_engine
        elif default_engine.exists() and default_engine.stat().st_size > 50000:
            chosen_model = default_engine
        elif test_engine.exists() and test_engine.stat().st_size > 50000:
            chosen_model = test_engine
        elif v2_onnx.exists():
            chosen_model = v2_onnx
        elif onnx_path.exists():
            chosen_model = onnx_path
        else:
            chosen_model = v2_engine

        self.model_path = chosen_model

        # Recipe 초기 경로 결정
        if recipe_path:
            self.recipe_path = Path(recipe_path)
        else:
            self.recipe_path = resolve_recipe_path(self.ai_dir)

        self.recipe = {}
        self._load_recipe()

        # Detector 로드
        self.detector = Detector(str(self.model_path))
        self._update_name_mappings()

    def _load_recipe(self) -> None:
        """현재 self.recipe_path의 JSON을 로드합니다."""
        if self.recipe_path.exists():
            try:
                with open(self.recipe_path, "r", encoding="utf-8") as f:
                    self.recipe = json.load(f)
            except Exception as e:
                print(f"[AI Judge] 레시피 로드 실패 ({self.recipe_path}): {e}")
                self.recipe = {}
        else:
            self.recipe = {}

    def set_product(self, product_name: str = "", product_id: str = "") -> str:
        """선택된 제품에 매칭되는 레시피(.json)로 교체합니다."""
        target_path = resolve_recipe_path(self.ai_dir, product_name, product_id)
        if target_path != self.recipe_path or not self.recipe:
            self.recipe_path = target_path
            self._load_recipe()
            print(f"[AI Judge] 제품 '{product_name}' ({product_id}) 레시피 적용: {self.recipe_path.name}")
        return self.recipe_path.name

    def _update_name_mappings(self) -> None:
        names = getattr(self.detector, "names", {}) or getattr(
            self.detector.model, "names", {}
        )
        if isinstance(names, dict):
            self.name_to_id = {name: cid for cid, name in names.items()}
        elif isinstance(names, (list, tuple)):
            self.name_to_id = {name: cid for cid, name in enumerate(names)}
        else:
            self.name_to_id = {}

    def predict(
        self,
        frame,
        step_no: int = 1,
        product_name: str = "",
        product_id: str = "",
    ) -> JudgeResult:
        if product_name or product_id:
            self.set_product(product_name, product_id)

        if frame is None or (isinstance(frame, str) and frame == "mock_frame"):
            return JudgeResult(
                "FAIL",
                0.0,
                "입력 카메라 영상 프레임이 없습니다.",
                reasons=["영상 프레임 없음"],
                step_no=step_no,
            )

        # CameraThread에서 config.CAMERA_FLIP으로 이미 방향이 정렬되었으므로 원본 프레임 사용
        proc_frame = frame

        annotated_frame = proc_frame.copy() if hasattr(proc_frame, "copy") else proc_frame

        # 1. YOLO 추론
        detections = self.detector.detect(proc_frame)
        if not getattr(self, "name_to_id", None):
            self._update_name_mappings()

        step_key = str(step_no)
        step_config = self.recipe.get(step_key)

        # 레시피에 해당 STEP이 정의되어 있지 않은 경우
        if not step_config:
            for d in detections:
                box = d["bbox"]
                cid = d["class_id"]
                cname = getattr(self.detector.model, "names", {}).get(cid, str(cid))
                if cv2 is not None:
                    bx1, by1, bx2, by2 = map(int, box)
                    cv2.rectangle(annotated_frame, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
                    _draw_box_label(annotated_frame, cname, bx1, by1, (0, 255, 0))
            return JudgeResult(
                "PASS",
                0.95,
                f"STEP {step_no} (레시피 미정의 단계: 객체 {len(detections)}건 검출 통과)",
                reasons=[f"객체 {len(detections)}건 검출 확인"],
                annotated_frame=annotated_frame,
                step_no=step_no,
            )

        reference_name = step_config.get("reference")
        target_configs = step_config.get("targets", [])

        ref_cid = self.name_to_id.get(reference_name)
        reference = find_by_class(detections, ref_cid) if ref_cid is not None else None

        fail_reasons = []
        fail_reasons_ascii = []
        pass_details = []
        confidences = []

        # 2. Reference 검출 여부 확인
        if reference is None:
            fail_reasons.append(f"기준 부품(Reference) 미검출: {reference_name}")
            fail_reasons_ascii.append(f"REF MISSING: {reference_name}")
        else:
            confidences.append(reference.get("confidence", 0.9))
            rx1, ry1, rx2, ry2 = map(int, reference["bbox"])
            if cv2 is not None:
                # Reference: 파란색 바운딩 박스
                cv2.rectangle(annotated_frame, (rx1, ry1), (rx2, ry2), (255, 0, 0), 2)
                _draw_box_label(annotated_frame, f"REF: {reference_name}", rx1, ry1, (255, 120, 0))

            # 3. 각 Target 부품 검사
            for target_config in target_configs:
                target_name = target_config["class"]
                target_cid = self.name_to_id.get(target_name)
                required_count = target_config.get("required_count", 1)

                targets = (
                    find_all_by_class(detections, target_cid)
                    if target_cid is not None
                    else []
                )

                # Target 개수 부족 판정
                if len(targets) < required_count:
                    fail_reasons.append(
                        f"부품 누락: {target_name} (검출 {len(targets)} / 필요 {required_count})"
                    )
                    fail_reasons_ascii.append(
                        f"MISSING: {target_name} ({len(targets)}/{required_count})"
                    )
                    continue

                for t in targets:
                    confidences.append(t.get("confidence", 0.9))

                # 상대 좌표 계산
                relative_results = []
                for t in targets:
                    rel_x, rel_y = get_relative_center(t["bbox"], reference["bbox"])
                    relative_results.append(
                        {
                            "target": t,
                            "relative_x": rel_x,
                            "relative_y": rel_y,
                        }
                    )

                # 복수 위치 배정 (positions)
                if "positions" in target_config:
                    positions = target_config["positions"]
                    matched_results = match_multiple_positions(
                        relative_results, positions
                    )

                    if matched_results is None:
                        fail_reasons.append(f"위치 매칭 실패: {target_name}")
                        fail_reasons_ascii.append(f"MATCH FAIL: {target_name}")
                        continue

                    for i, pos in enumerate(positions):
                        m_res = matched_results[i]
                        rel_x = m_res["relative_x"]
                        rel_y = m_res["relative_y"]
                        pos_ok = check_relative_position(
                            rel_x,
                            rel_y,
                            pos["expected_x"],
                            pos["expected_y"],
                            pos["tolerance_x"],
                            pos["tolerance_y"],
                        )

                        t_box = m_res["target"]["bbox"]
                        bx1, by1, bx2, by2 = map(int, t_box)

                        if pos_ok:
                            pass_details.append(f"{target_name}[{i+1}] 위치 정상")
                            color = (0, 255, 0)
                        else:
                            fail_reasons.append(f"{target_name}[{i+1}] 조립 위치 오차 초과")
                            fail_reasons_ascii.append(f"POS ERROR: {target_name}[{i+1}]")
                            color = (0, 0, 255)

                        if cv2 is not None:
                            cv2.rectangle(annotated_frame, (bx1, by1), (bx2, by2), color, 2)
                            _draw_box_label(annotated_frame, f"{target_name}[{i+1}]", bx1, by1, color)

                # 단일 위치 검사
                else:
                    exp_x = target_config["expected_x"]
                    exp_y = target_config["expected_y"]
                    tol_x = target_config["tolerance_x"]
                    tol_y = target_config["tolerance_y"]

                    # 기대 위치에 가장 가까운 검출 선택
                    best_result = min(
                        relative_results,
                        key=lambda r: (r["relative_x"] - exp_x) ** 2
                        + (r["relative_y"] - exp_y) ** 2,
                    )

                    rel_x = best_result["relative_x"]
                    rel_y = best_result["relative_y"]
                    pos_ok = check_relative_position(
                        rel_x, rel_y, exp_x, exp_y, tol_x, tol_y
                    )

                    bx1, by1, bx2, by2 = map(int, best_result["target"]["bbox"])
                    if pos_ok:
                        pass_details.append(f"{target_name} 위치 정상")
                        color = (0, 255, 0)
                    else:
                        fail_reasons.append(f"{target_name} 조립 위치 오차 초과")
                        fail_reasons_ascii.append(f"POS ERROR: {target_name}")
                        color = (0, 0, 255)

                    if cv2 is not None:
                        cv2.rectangle(annotated_frame, (bx1, by1), (bx2, by2), color, 2)
                        _draw_box_label(annotated_frame, target_name, bx1, by1, color)

        # 4. 최종 판정 및 화면 시각화
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.90

        if not fail_reasons:
            final_res = "PASS"
            detail = f"STEP {step_no} 정상 조립 확인 (검증 항목: {len(pass_details)}건)"
            if cv2 is not None:
                # 좌측 여백(x1=60, y1=40)을 두어 글씨가 좌측 테두리에 짤리지 않도록 보정
                cv2.rectangle(annotated_frame, (60, 40), (250, 110), (0, 0, 0), -1)
                cv2.rectangle(annotated_frame, (60, 40), (250, 110), (0, 255, 0), 3)
                cv2.putText(
                    annotated_frame,
                    "PASS",
                    (88, 92),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.4,
                    (0, 255, 0),
                    3,
                )
            reasons = pass_details if pass_details else ["모든 조립 기준 적합"]
        else:
            final_res = "FAIL"
            detail = f"STEP {step_no} 불량: {fail_reasons[0]}"
            if cv2 is not None:
                # 좌측 여백(x1=60, y1=40)을 두어 글씨가 좌측 테두리에 짤리지 않도록 보정
                cv2.rectangle(annotated_frame, (60, 40), (250, 110), (0, 0, 0), -1)
                cv2.rectangle(annotated_frame, (60, 40), (250, 110), (0, 0, 255), 3)
                cv2.putText(
                    annotated_frame,
                    "FAIL",
                    (92, 92),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.4,
                    (0, 0, 255),
                    3,
                )
                y_pos = 150
                for r in fail_reasons_ascii[:3]:
                    (rw, rh), baseline = cv2.getTextSize(r, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    cv2.rectangle(
                        annotated_frame,
                        (60, y_pos - rh - 4),
                        (65 + rw, y_pos + baseline + 2),
                        (0, 0, 0),
                        -1,
                    )
                    cv2.putText(
                        annotated_frame,
                        r,
                        (65, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 255),
                        2,
                    )
                    y_pos += 36
            reasons = fail_reasons

        return JudgeResult(
            result=final_res,
            confidence=avg_conf,
            detail=detail,
            reasons=reasons,
            annotated_frame=annotated_frame,
            step_no=step_no,
        )


def create_judge(backend: Optional[str] = None) -> BaseJudge:
    """설정값에 따라 AI 구현체를 생성합니다. 오류 시 MockJudge로 안전하게 자동 전환합니다."""
    selected = (backend or config.AI_BACKEND).lower()
    if config.TEST_MODE or selected == "mock":
        return MockJudge()

    if selected in ("tensorrt", "trt", "engine", "yolo", "actual"):
        try:
            return TensorRTJudge()
        except Exception as error:
            print(
                f"\n⚠️ [AI Judge 경고] 실제 AI 모델/엔진 로드 실패 ({error})\n"
                f"   원인: NVIDIA GPU 드라이버 버전 불일치 또는 TensorRT 엔진 로드 오류\n"
                f"   조치: MockJudge(테스트 판정기)로 안전하게 자동 전환하여 실행합니다.\n"
            )
            return MockJudge()

    return MockJudge()


class AiInferenceThread(QThread):
    """최신 Camera Frame과 현재 STEP 번호를 받아 비동기로 추론을 수행합니다."""

    judgement_ready = pyqtSignal(object)
    status_changed = pyqtSignal(str, bool)

    def __init__(self, judge: Optional[BaseJudge] = None, parent=None):
        super().__init__(parent)
        self.judge = judge or create_judge()
        self._condition = threading.Condition()
        self._latest_frame = None
        self._latest_step = 1
        self._latest_product_name = ""
        self._latest_product_id = ""
        self._running = False

    def is_ready(self) -> bool:
        return self._running and self.isRunning()

    def restart(self) -> None:
        self.stop()
        self.start()

    def set_product(self, product_name: str = "", product_id: str = "") -> str:
        """현재 작업 대상 제품을 설정하고 레시피를 동기화합니다."""
        with self._condition:
            self._latest_product_name = product_name
            self._latest_product_id = product_id
        if hasattr(self.judge, "set_product"):
            return self.judge.set_product(product_name, product_id)
        return ""

    def submit_frame(
        self,
        frame,
        step_no: int = 1,
        product_name: str = "",
        product_id: str = "",
    ) -> None:
        """대기열을 늘리지 않고 최신 Frame과 STEP 번호, 제품명을 저장합니다."""
        with self._condition:
            self._latest_frame = frame
            self._latest_step = int(step_no)
            if product_name:
                self._latest_product_name = product_name
            if product_id:
                self._latest_product_id = product_id
            self._condition.notify()

    def run(self) -> None:
        self._running = True
        self.status_changed.emit("AI 판정 준비 완료", True)
        while self._running:
            with self._condition:
                while self._running and self._latest_frame is None:
                    self._condition.wait(timeout=0.5)
                if not self._running:
                    break
                frame = self._latest_frame
                step_no = self._latest_step
                pname = self._latest_product_name
                pid = self._latest_product_id
                self._latest_frame = None
            try:
                result = self.judge.predict(
                    frame, step_no=step_no, product_name=pname, product_id=pid
                )
                self.judgement_ready.emit(result)
            except Exception as error:
                self.status_changed.emit(f"AI 추론 오류: {error}", False)

    def stop(self) -> None:
        self._running = False
        with self._condition:
            self._condition.notify_all()
        if self.isRunning():
            self.wait(3000)
