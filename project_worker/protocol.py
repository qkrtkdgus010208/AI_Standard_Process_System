"""TCP와 UART 메시지 형식을 한 곳에서 관리합니다."""

import base64
import binascii
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ProtocolMessage:
    """구분자로 분해한 수신 메시지입니다."""

    command: str
    arguments: Tuple[str, ...]
    raw: str


def parse_message(raw_message: str) -> ProtocolMessage:
    """`COMMAND|VALUE` 형식의 메시지를 안전하게 파싱합니다."""
    cleaned = raw_message.strip()
    if not cleaned:
        return ProtocolMessage("", (), raw_message)
    parts = [part.strip() for part in cleaned.split("|")]
    return ProtocolMessage(parts[0].upper(), tuple(parts[1:]), cleaned)


def decode_message_text(encoded_text: str) -> str:
    """Monitoring PC가 Base64로 보낸 UTF-8 직원 메시지를 복원합니다."""
    try:
        return base64.urlsafe_b64decode(encoded_text.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeError, binascii.Error):
        return ""
