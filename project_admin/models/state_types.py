"""작업자 인증과 상태 저장에서 공유하는 dict 계약입니다.

TCP JSON과 PyQt signal은 런타임 호환을 위해 dict를 유지하고, TypedDict로
필드 이름과 값의 의미를 코드 리뷰 및 정적 분석 도구에 명시합니다.
"""

from __future__ import annotations

from typing import TypedDict
try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired


class EmployeeIdentity(TypedDict):
    employee_id: str
    name: str
    role: str


class WorkerStateInput(TypedDict):
    employee_id: str
    name: NotRequired[str]
    product_id: str
    product_name: str
    state: str
    current_step: int
    total_steps: int
    last_result: str
    event: NotRequired[str]
    defect_type: NotRequired[str]
    detail: NotRequired[str]
    client_event_id: NotRequired[str | None]


class StateRequest(TypedDict, total=False):
    type: str
    token: str
    event_id: str | None
    product_id: str
    product_name: str
    state: str
    current_step: int
    total_steps: int
    last_result: str
    event: str
    defect_type: str
    detail: str


class GatewaySession(TypedDict):
    employee: EmployeeIdentity
    client_ip: str
