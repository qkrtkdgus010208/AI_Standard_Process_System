def get_relative_center(
    target_bbox, reference_bbox
):  # reference의 중심을 기준으로 target의 중심 위치를 상대적으로 계산
    tx1, ty1, tx2, ty2 = target_bbox
    rx1, ry1, rx2, ry2 = reference_bbox

    target_cx = (tx1 + tx2) / 2
    target_cy = (ty1 + ty2) / 2

    reference_cx = (rx1 + rx2) / 2
    reference_cy = (ry1 + ry2) / 2

    reference_width = rx2 - rx1
    reference_height = ry2 - ry1

    relative_x = (target_cx - reference_cx) / reference_width
    relative_y = (reference_cy - target_cy) / reference_height

    return relative_x, relative_y
