"""AI 품질 판정 결과를 표시하는 전용 다이얼로그 모듈입니다.

창의 좌측에는 바운딩 박스가 그려진 캡처 사진을 표시하고,
우측 상단에는 판정 결과(PASS/FAIL 및 신뢰도),
우측 하단에는 세부 항목별 판정 사유를 보기 쉽게 표시합니다.
"""

import re
from datetime import datetime
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

try:
    import cv2
except ImportError:
    cv2 = None

_RE_COORD_LABELED = re.compile(r"\s*\([^)]*(?:x[:=]|y[:=]|측정|기준|actual|expected)[^)]*\)")
_RE_COORD_NUMERIC = re.compile(r"\s*\([+-]?\d+\.?\d*,\s*[+-]?\d+\.?\d*\)")


class AiResultDialog(QDialog):
    """AI 조립 검사 결과를 시각화하여 작업자에게 안내하는 팝업 창입니다."""

    def __init__(
        self,
        result,
        step_no: int = 1,
        product_name: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.result = result
        self.step_no = step_no
        self.product_name = product_name or "제품 조립 검사"

        self.setWindowTitle(f"AI 품질 판정 결과 - STEP {self.step_no}")
        self.setMinimumSize(980, 620)
        self.resize(1060, 680)

        self._create_ui()
        self._populate_data()

    def _create_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # ── 상단 헤더 ────────────────────────────────────────────────────────
        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(4)

        eyebrow = QLabel("AI QUALITY INSPECTION  ·  DETAIL RESULT")
        eyebrow.setStyleSheet("color:#6F7B89; font-size:11px; font-weight:700; letter-spacing:1px;")

        title = QLabel(f"STEP {self.step_no} 공정 조립 판정 결과")
        title.setObjectName("pageTitle")
        title.setStyleSheet("color:#18212C; font-size:22px; font-weight:700;")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subtitle = QLabel(f"제품명: {self.product_name}    |    검사 일시: {now_str}")
        subtitle.setStyleSheet("color:#6F7B89; font-size:13px;")

        header_text.addWidget(eyebrow)
        header_text.addWidget(title)
        header_text.addWidget(subtitle)

        header_layout.addLayout(header_text)
        header_layout.addStretch()

        close_btn_top = QPushButton("닫기 (ESC)")
        close_btn_top.setFixedHeight(36)
        close_btn_top.clicked.connect(self.accept)
        header_layout.addWidget(close_btn_top)

        main_layout.addLayout(header_layout)

        # ── 본문 레이아웃 (좌측: 영상, 우측: 판정 및 사유) ───────────────────
        body_layout = QHBoxLayout()
        body_layout.setSpacing(18)

        # 좌측 패널 (박스 쳐진 사진)
        left_card = QFrame()
        left_card.setObjectName("card")
        left_card.setStyleSheet("background:#FFFFFF; border:1px solid #DDE3EA; border-radius:9px;")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)

        left_title = QLabel("검사 캡처 영상 (AI 객체 검출 및 위치 측정)")
        left_title.setStyleSheet("color:#202936; font-size:14px; font-weight:700;")
        left_layout.addWidget(left_title)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setStyleSheet("background:#0F172A; border-radius:6px; border:1px solid #334155;")
        self.image_label.setMinimumSize(520, 400)
        left_layout.addWidget(self.image_label, stretch=1)

        legend_label = QLabel("■ 파란색: 기준 부품(Reference)  |  ■ 초록색: 정상 조립  |  ■ 빨간색: 불량/오차")
        legend_label.setStyleSheet("color:#64748B; font-size:12px;")
        legend_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(legend_label)

        body_layout.addWidget(left_card, stretch=6)

        # 우측 패널 (상단: 결과 카드, 하단: 상세 사유 목록)
        right_panel = QVBoxLayout()
        right_panel.setSpacing(14)

        # 1. 판정 결과 카드 (우측 상단)
        result_card = QFrame()
        result_card.setObjectName("card")
        result_card.setStyleSheet("background:#FFFFFF; border:1px solid #DDE3EA; border-radius:9px;")
        res_card_layout = QVBoxLayout(result_card)
        res_card_layout.setContentsMargins(18, 16, 18, 16)
        res_card_layout.setSpacing(10)

        res_header = QLabel("최종 판정 결과")
        res_header.setStyleSheet("color:#475569; font-size:12px; font-weight:700;")
        res_card_layout.addWidget(res_header)

        self.badge_label = QLabel("PASS")
        self.badge_label.setAlignment(Qt.AlignCenter)
        self.badge_label.setFixedHeight(64)
        res_card_layout.addWidget(self.badge_label)

        metrics_layout = QHBoxLayout()
        self.metric_step = QLabel(f"검사 단계: STEP {self.step_no}")
        self.metric_step.setStyleSheet("color:#475569; font-size:13px; font-weight:600;")

        metrics_layout.addWidget(self.metric_step)
        metrics_layout.addStretch()
        res_card_layout.addLayout(metrics_layout)

        right_panel.addWidget(result_card, stretch=0)

        # 2. 판정 상세 사유 카드 (우측 하단)
        reason_card = QFrame()
        reason_card.setObjectName("card")
        reason_card.setStyleSheet("background:#FFFFFF; border:1px solid #DDE3EA; border-radius:9px;")
        reason_layout = QVBoxLayout(reason_card)
        reason_layout.setContentsMargins(18, 16, 18, 16)
        reason_layout.setSpacing(10)

        reason_title = QLabel("세부 검사 내역 및 사유")
        reason_title.setStyleSheet("color:#202936; font-size:14px; font-weight:700;")
        reason_layout.addWidget(reason_title)

        self.reason_list = QListWidget()
        self.reason_list.setStyleSheet(
            "QListWidget { background:#F8FAFC; border:1px solid #E2E8F0; border-radius:6px; outline:none; }"
            "QListWidget::item { padding:8px 10px; border-bottom:1px solid #EDF2F7; font-size:13px; }"
        )
        reason_layout.addWidget(self.reason_list, stretch=1)

        right_panel.addWidget(reason_card, stretch=1)

        # 확인 버튼
        confirm_btn = QPushButton("확인 (Space / Enter)")
        confirm_btn.setObjectName("primaryButton")
        confirm_btn.setStyleSheet(
            "QPushButton { min-height:42px; color:#FFFFFF; background:#2563EB; "
            "border:1px solid #1D4ED8; border-radius:6px; font-size:14px; font-weight:700; }"
            "QPushButton:hover { background:#1D4ED8; }"
        )
        confirm_btn.clicked.connect(self.accept)
        confirm_btn.setDefault(True)
        right_panel.addWidget(confirm_btn)

        body_layout.addLayout(right_panel, stretch=4)
        main_layout.addLayout(body_layout, stretch=1)

    def _clean_reason_text(self, text: str) -> str:
        """(x:..., y:...) 또는 (측정:... / 기준:...) 등의 좌표 수치를 사유에서 제거합니다."""
        if not text:
            return ""
        cleaned = _RE_COORD_LABELED.sub("", text)
        cleaned = _RE_COORD_NUMERIC.sub("", cleaned)
        return cleaned.strip()

    def _populate_data(self) -> None:
        """전달받은 판정 결과를 UI 위젯들에 바인딩합니다."""
        is_pass = str(getattr(self.result, "result", "")).upper() == "PASS"
        reasons = getattr(self.result, "reasons", [])
        detail = getattr(self.result, "detail", "")
        annotated_frame = getattr(self.result, "annotated_frame", None)

        # 1. 뱃지 스타일링
        if is_pass:
            self.badge_label.setText("PASS")
            self.badge_label.setStyleSheet(
                "background:#DCFCE7; color:#15803D; border:2px solid #22C55E; "
                "border-radius:8px; font-size:32px; font-weight:900; letter-spacing:3px;"
            )
        else:
            self.badge_label.setText("FAIL")
            self.badge_label.setStyleSheet(
                "background:#FEE2E2; color:#B91C1C; border:2px solid #EF4444; "
                "border-radius:8px; font-size:32px; font-weight:900; letter-spacing:3px;"
            )

        # 2. 이미지 바인딩
        if annotated_frame is not None and cv2 is not None:
            self._set_frame_image(annotated_frame)
        else:
            self.image_label.setText("판정 영상 이미지가 없습니다.")
            self.image_label.setStyleSheet("color:#94A3B8; font-size:14px; background:#0F172A;")

        # 3. 사유 목록 바인딩 (좌표 값 제거 적용)
        self.reason_list.clear()

        if is_pass:
            pass_item = QListWidgetItem("✓ 모든 부품 및 상대 위치 검증을 통과했습니다.")
            pass_item.setForeground(QColor("#15803D"))
            font = pass_item.font()
            font.setBold(True)
            pass_item.setFont(font)
            self.reason_list.addItem(pass_item)

            if reasons:
                for reason in reasons:
                    cleaned = self._clean_reason_text(str(reason))
                    item = QListWidgetItem(f"   · {cleaned}")
                    item.setForeground(QColor("#2F7651"))
                    self.reason_list.addItem(item)
            elif detail:
                cleaned = self._clean_reason_text(str(detail))
                item = QListWidgetItem(f"   · 세부: {cleaned}")
                item.setForeground(QColor("#334155"))
                self.reason_list.addItem(item)
        else:
            fail_title = QListWidgetItem("✗ 조립 품질 검사 기준 미달 항목이 발견되었습니다.")
            fail_title.setForeground(QColor("#B91C1C"))
            font = fail_title.font()
            font.setBold(True)
            fail_title.setFont(font)
            self.reason_list.addItem(fail_title)

            if reasons:
                for reason in reasons:
                    cleaned = self._clean_reason_text(str(reason))
                    item = QListWidgetItem(f"   · {cleaned}")
                    item.setForeground(QColor("#DC2626"))
                    self.reason_list.addItem(item)
            elif detail:
                cleaned = self._clean_reason_text(str(detail))
                item = QListWidgetItem(f"   · {cleaned}")
                item.setForeground(QColor("#DC2626"))
                self.reason_list.addItem(item)
            else:
                item = QListWidgetItem("   · 부품 누락 또는 상대 위치 허용 오차 초과")
                item.setForeground(QColor("#DC2626"))
                self.reason_list.addItem(item)

    def _set_frame_image(self, frame) -> None:
        """OpenCV BGR Frame을 QPixmap으로 변환하여 라벨에 맞게 표시합니다."""
        try:
            self._annotated_frame = frame
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            q_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self._cached_pixmap = QPixmap.fromImage(q_image)
            self._update_scaled_image()
        except Exception as e:
            self.image_label.setText(f"이미지 변환 실패: {e}")

    def _update_scaled_image(self) -> None:
        """캐시된 Pixmap을 현재 라벨 크기에 맞추어 부드럽게 스케일링합니다."""
        if not hasattr(self, "_cached_pixmap") or self._cached_pixmap is None or self._cached_pixmap.isNull():
            return
        target_size = self.image_label.contentsRect().size()
        if target_size.width() <= 10 or target_size.height() <= 10:
            target_size = self.image_label.size()

        scaled_pixmap = self._cached_pixmap.scaled(
            target_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled_pixmap)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._update_scaled_image()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_scaled_image()
