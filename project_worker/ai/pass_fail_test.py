import json
import os
import subprocess
import sys

import cv2

from detector import Detector
from inspector import (
    find_by_class,
    find_all_by_class,
    check_relative_position,
    match_multiple_positions,
)
from normalizer import get_relative_center

# ============================================================
# 0. 검사할 STEP
# ============================================================

STEP = 6


# ============================================================
# 1. Recipe 로드
# ============================================================

# 인자 또는 환경변수로부터 레시피 파일 선택 (기본값: racing_car.json)
recipe_arg = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("RECIPE_FILE", "racing_car.json")
if not os.path.exists(recipe_arg):
    if os.path.exists(f"{recipe_arg}.json"):
        recipe_arg = f"{recipe_arg}.json"
    elif os.path.exists("racing_car.json"):
        recipe_arg = "racing_car.json"
    elif os.path.exists("pickup_truck.json"):
        recipe_arg = "pickup_truck.json"
    else:
        recipe_arg = "recipe.json"
recipe_file = recipe_arg
print(f"[Recipe] 로드된 레시피 파일: {recipe_file}")
with open(recipe_file, "r", encoding="utf-8") as f:
    recipe = json.load(f)

step_config = recipe[str(STEP)]

reference_name = step_config["reference"]
target_configs = step_config["targets"]


# ============================================================
# 2. Detector 생성 (config.AI_ENGINE_MODEL 기반)
# ============================================================

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_dir = os.path.abspath(os.path.join(_script_dir, ".."))
if _project_dir not in sys.path:
    sys.path.insert(0, _project_dir)

try:
    import config
    engine_model_name = getattr(config, "AI_ENGINE_MODEL", "yollo26n_fp32.engine")
except ImportError:
    engine_model_name = "yollo26n_fp32.engine"

model_file = os.path.join(_script_dir, engine_model_name)
if not os.path.exists(model_file):
    model_file = engine_model_name
detector = Detector(model_file)
print(f"[Detector] 로드된 모델: {model_file}")


# ============================================================
# 3. class name -> class id
# ============================================================

name_to_id = {name: class_id for class_id, name in detector.model.names.items()}

reference_class_id = name_to_id[reference_name]

target_class_ids = {
    target["class"]: name_to_id[target["class"]] for target in target_configs
}


print(f"STEP {STEP}")
print(f"Reference : {reference_name}")

for target in target_configs:
    print(f"Target    : {target['class']} " f"x{target.get('required_count', 1)}")


# ============================================================
# 4. 카메라 연결
# ============================================================

cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)

cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not cap.isOpened():
    print("카메라를 열 수 없습니다.")
    exit()


# ============================================================
# 5. 카메라 초기화
# ============================================================

print("카메라 초기화 중...")

for _ in range(30):
    cap.read()


# ============================================================
# 6. 카메라 설정 (C270 v4l2-ctl 하드웨어 설정)
# ============================================================

try:
    subprocess.run([
        "v4l2-ctl",
        "-d", "/dev/video0",
        "-c", "auto_exposure=1",
        "-c", "exposure_time_absolute=200",
        "-c", "contrast=22",
        "-c", "sharpness=255"
    ], check=True)
    print("[Camera] v4l2-ctl C270 카메라 설정 적용 완료")
except Exception as e:
    print(f"[Camera] v4l2-ctl 설정 건너뜀/실패 (OpenCV 설정 유지): {e}")

cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)

cap.set(cv2.CAP_PROP_EXPOSURE, -6)

cap.set(cv2.CAP_PROP_CONTRAST, 22)

cap.set(cv2.CAP_PROP_SHARPNESS, 255)


for _ in range(10):
    cap.read()


cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)

cap.set(cv2.CAP_PROP_EXPOSURE, -6)

cap.set(cv2.CAP_PROP_CONTRAST, 22)

cap.set(cv2.CAP_PROP_SHARPNESS, 255)


print("카메라 준비 완료")

print()
print("SPACE : 현재 STEP 검사")
print("R     : 실시간 화면 복귀")
print("Q     : 종료")


# ============================================================
# 7. 카메라 실행
# ============================================================

detected_frame = None


while True:

    # ========================================================
    # 검사 결과 화면
    # ========================================================

    if detected_frame is not None:

        cv2.imshow("Assembly Inspection", detected_frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("r"):
            detected_frame = None

        elif key == ord("q"):
            break

        continue

    # ========================================================
    # 실시간 화면
    # ========================================================

    ret, frame = cap.read()

    if not ret:
        print("카메라 프레임을 읽을 수 없습니다.")
        break

    # 데이터셋 촬영 방향과 동일
    frame = cv2.flip(frame, -1)

    display = frame.copy()

    cv2.putText(
        display, f"STEP {STEP}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2
    )

    cv2.putText(
        display,
        "SPACE: INSPECT / Q: QUIT",
        (20, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        2,
    )

    cv2.imshow("Assembly Inspection", display)

    key = cv2.waitKey(1) & 0xFF

    # ========================================================
    # SPACE : 현재 STEP 검사
    # ========================================================

    if key == ord(" "):

        detections = detector.detect(frame)

        detected_frame = frame.copy()

        fail_reasons = []

        print()
        print("========================================")
        print(f"STEP {STEP} 검사")
        print("========================================")

        # ====================================================
        # Reference 찾기
        # ====================================================

        reference = find_by_class(detections, reference_class_id)

        # ====================================================
        # Reference 미검출
        # ====================================================

        if reference is None:

            fail_reasons.append(f"REF MISSING: {reference_name}")

            print(f"[FAIL] Reference 미검출: " f"{reference_name}")

        # ====================================================
        # Reference 검출
        # ====================================================

        else:

            # Reference bbox 표시
            rx1, ry1, rx2, ry2 = map(int, reference["bbox"])

            cv2.rectangle(detected_frame, (rx1, ry1), (rx2, ry2), (255, 0, 0), 2)

            cv2.putText(
                detected_frame,
                f"REF: {reference_name}",
                (rx1, max(20, ry1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 0, 0),
                2,
            )

            # =================================================
            # 각 Target 검사
            # =================================================

            for target_config in target_configs:

                target_name = target_config["class"]

                required_count = target_config.get("required_count", 1)

                targets = find_all_by_class(detections, target_class_ids[target_name])

                print()
                print(
                    f"[{target_name}] "
                    f"검출: {len(targets)} / "
                    f"필요: {required_count}"
                )

                # =============================================
                # Target 개수 부족
                # =============================================

                if len(targets) < required_count:

                    fail_reasons.append(
                        f"MISSING: {target_name} " f"({len(targets)}/{required_count})"
                    )

                    print(f"[FAIL] {target_name} " f"개수 부족")

                    continue

                # =============================================
                # 검출된 Target들의 상대좌표 계산
                # =============================================

                relative_results = []

                for target in targets:

                    relative_x, relative_y = get_relative_center(
                        target["bbox"], reference["bbox"]
                    )

                    relative_results.append(
                        {
                            "target": target,
                            "relative_x": relative_x,
                            "relative_y": relative_y,
                        }
                    )

                # =============================================
                # 동일 클래스 여러 개
                # positions가 존재하는 경우
                # =============================================

                if "positions" in target_config:

                    positions = target_config["positions"]

                    matched_results = match_multiple_positions(
                        relative_results, positions
                    )

                    if matched_results is None:

                        fail_reasons.append(f"MATCH FAIL: {target_name}")

                        continue

                    # =========================================
                    # 각 위치 검사
                    # =========================================

                    for i in range(len(positions)):

                        result = matched_results[i]

                        position = positions[i]

                        relative_x = result["relative_x"]
                        relative_y = result["relative_y"]

                        position_ok = check_relative_position(
                            relative_x,
                            relative_y,
                            position["expected_x"],
                            position["expected_y"],
                            position["tolerance_x"],
                            position["tolerance_y"],
                        )

                        print(
                            f"Position {i + 1}: "
                            f"actual=({relative_x:.4f}, "
                            f"{relative_y:.4f}) "
                            f"expected=("
                            f"{position['expected_x']:.4f}, "
                            f"{position['expected_y']:.4f})"
                        )

                        if position_ok:

                            print(" -> PASS")

                        else:

                            print(" -> FAIL")

                            fail_reasons.append(f"POSITION: " f"{target_name}[{i + 1}]")

                        # -------------------------------------
                        # bbox 표시
                        # -------------------------------------

                        target = result["target"]

                        tx1, ty1, tx2, ty2 = map(int, target["bbox"])

                        if position_ok:
                            color = (0, 255, 0)

                        else:
                            color = (0, 0, 255)

                        cv2.rectangle(detected_frame, (tx1, ty1), (tx2, ty2), color, 2)

                        cv2.putText(
                            detected_frame,
                            f"{target_name}[{i + 1}]",
                            (tx1, max(20, ty1 - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            color,
                            2,
                        )

                # =============================================
                # 일반 Target 1개
                # =============================================

                else:

                    # 정상 위치에 가장 가까운 검출 사용
                    best_result = None
                    best_difference = float("inf")

                    for result in relative_results:

                        dx = result["relative_x"] - target_config["expected_x"]

                        dy = result["relative_y"] - target_config["expected_y"]

                        difference = dx * dx + dy * dy

                        if difference < best_difference:

                            best_difference = difference

                            best_result = result

                    relative_x = best_result["relative_x"]

                    relative_y = best_result["relative_y"]

                    position_ok = check_relative_position(
                        relative_x,
                        relative_y,
                        target_config["expected_x"],
                        target_config["expected_y"],
                        target_config["tolerance_x"],
                        target_config["tolerance_y"],
                    )

                    print(f"actual=({relative_x:.4f}, " f"{relative_y:.4f})")

                    print(
                        f"expected=("
                        f"{target_config['expected_x']:.4f}, "
                        f"{target_config['expected_y']:.4f})"
                    )

                    if position_ok:

                        print(" -> PASS")

                    else:

                        print(" -> FAIL")

                        fail_reasons.append(f"POSITION: {target_name}")

                    # -----------------------------------------
                    # bbox 표시
                    # -----------------------------------------

                    target = best_result["target"]

                    tx1, ty1, tx2, ty2 = map(int, target["bbox"])

                    if position_ok:
                        color = (0, 255, 0)

                    else:
                        color = (0, 0, 255)

                    cv2.rectangle(detected_frame, (tx1, ty1), (tx2, ty2), color, 2)

                    cv2.putText(
                        detected_frame,
                        target_name,
                        (tx1, max(20, ty1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        color,
                        2,
                    )

        # ====================================================
        # 최종 판정
        # ====================================================

        if not fail_reasons:

            print()
            print("============== PASS ==============")

            cv2.putText(
                detected_frame,
                "PASS",
                (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,
                (0, 255, 0),
                4,
            )

        else:

            print()
            print("============== FAIL ==============")

            for reason in fail_reasons:
                print(reason)

            cv2.putText(
                detected_frame,
                "FAIL",
                (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.5,
                (0, 0, 255),
                4,
            )

            # ================================================
            # FAIL 이유 화면 표시
            # ================================================

            text_y = 90

            for reason in fail_reasons:

                cv2.putText(
                    detected_frame,
                    reason,
                    (20, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2,
                )

                text_y += 30

        cv2.putText(
            detected_frame,
            "R: LIVE / Q: QUIT",
            (20, 700),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2,
        )

    # ========================================================
    # Q
    # ========================================================

    elif key == ord("q"):
        break


# ============================================================
# 8. 종료
# ============================================================

cap.release()
cv2.destroyAllWindows()
