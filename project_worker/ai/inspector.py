import itertools


def check_class_exists(detections, target_class_id):
    for obj in detections:
        if obj["class_id"] == target_class_id:
            return True

    return False


def find_by_class(detections, target_class_id):
    for obj in detections:
        if obj["class_id"] == target_class_id:
            return obj
    return None


def find_all_by_class(detections, target_class_id):
    results = []

    for obj in detections:
        if obj["class_id"] == target_class_id:
            results.append(obj)

    return results


def check_relative_position(
    relative_x, relative_y, expected_x, expected_y, tolerance_x, tolerance_y
):
    x_ok = abs(relative_x - expected_x) <= tolerance_x
    y_ok = abs(relative_y - expected_y) <= tolerance_y

    return x_ok and y_ok


def get_position_distance(relative_x, relative_y, position):
    tol_x = max(1e-6, position.get("tolerance_x", 1e-6))
    tol_y = max(1e-6, position.get("tolerance_y", 1e-6))
    dx = (relative_x - position["expected_x"]) / tol_x
    dy = (relative_y - position["expected_y"]) / tol_y

    return dx * dx + dy * dy


def match_multiple_positions(relative_results, positions):
    """
    동일 클래스의 여러 검출 결과를
    JSON의 여러 expected position에 가장 잘 맞게 배정
    """

    required_count = len(positions)

    if len(relative_results) < required_count:
        return None

    best_assignment = None
    best_score = float("inf")

    # 가능한 모든 배치 비교
    for indices in itertools.permutations(range(len(relative_results)), required_count):

        score = 0

        for position_index, detection_index in enumerate(indices):

            result = relative_results[detection_index]
            position = positions[position_index]

            score += get_position_distance(
                result["relative_x"], result["relative_y"], position
            )

        if score < best_score:
            best_score = score

            best_assignment = [relative_results[index] for index in indices]

    return best_assignment
