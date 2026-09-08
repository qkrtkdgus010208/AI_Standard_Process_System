"""시간 변환 및 포맷 유틸리티 모듈입니다."""

from typing import Optional


def format_seconds(seconds: Optional[int]) -> str:
    """초 단위 시간을 사용자가 읽기 쉬운 HH:MM:SS로 변환합니다."""
    if seconds is None:
        return "진행 중"
    hours, remainder = divmod(max(0, int(seconds)), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
