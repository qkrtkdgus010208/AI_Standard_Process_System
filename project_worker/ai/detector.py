from pathlib import Path
from ultralytics import YOLO

DEFAULT_NAMES = {
    0: "black_L_plate",
    1: "black_plate_1x6",
    2: "car_base",
    3: "driver_seat",
    4: "front_bumper",
    5: "front_windshield_roof",
    6: "rear_bumper",
    7: "rear_spoiler",
    8: "rear_windshield",
    9: "red_black_block_1x2",
    10: "steering_wheel",
}


class Detector:
    def __init__(self, model_path):
        self.model = YOLO(str(model_path), task="detect")
        self.names = DEFAULT_NAMES

    def detect(self, frame):
        results = self.model(frame, imgsz=640, conf=0.3, verbose=False)

        detections = []
        if not results or len(results) == 0 or results[0].boxes is None:
            return detections

        for box in results[0].boxes:
            detections.append(
                {
                    "class_id": int(box.cls.item()),
                    "confidence": float(box.conf.item()),
                    "bbox": box.xyxy[0].tolist(),
                }
            )

        return detections
