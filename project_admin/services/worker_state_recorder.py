"""작업자의 공정 상태 이벤트를 DB의 공정·STEP·Pause·판정·불량 테이블에 원자적으로 기록하는 서비스 모듈입니다.

DatabaseManager의 record_worker_state 책임을 분리하여 단일 책임 원칙(SRP)을 준수하고,
복잡한 상태 기계(State Machine) 전이 과정을 각 단계별 메서드로 명확히 분리합니다.
"""

from __future__ import annotations

import sqlite3
import uuid
from typing import Optional

from models.state_types import WorkerStateInput


class WorkerStateRecorder:
    """작업자 공정 상태 이벤트를 수신하여 SQLite 트랜잭션 내에 단계별로 반영하는 서비스입니다."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def record(self, state_data: WorkerStateInput) -> Optional[int]:
        """수신 상태를 검증 및 보존하고 공정·STEP·Pause·판정·불량 이력에 원자적으로 반영합니다."""
        (
            employee_id, product_id, product_name, state,
            last_result, event_name, defect_type, detail,
            current_step, total_steps, client_event_id,
        ) = self._validate_and_normalize(state_data)

        # 1. DB 엔티티 유효성 검증 (작업자 역할, 제품 등록 여부, STEP 범위)
        product = self._verify_db_entities(
            employee_id, product_id, current_step, total_steps, state
        )

        resolved_product_name = product_name or str(product["product_name"])
        event_values = (
            employee_id, product_id, resolved_product_name,
            state, current_step, total_steps, last_result,
            event_name, defect_type, detail,
        )

        # 2. worker_state_events 테이블에 이벤트 원문 기록 (중복 억제 포함)
        event_id = self._record_worker_event(
            event_values, employee_id, last_result, client_event_id
        )
        if event_id is None:
            return None

        # 3. idle 상태는 작업 선택/초기화 상태이므로 원문만 보존하고 제품 작업시간은 열지 않음
        if state == "idle":
            return event_id

        # 4. 진행 중인 product_run 조회 또는 신규 생성
        product_run_id = self._ensure_product_run(employee_id, product_id)

        # 5. 직전 STEP 정보 조회 및 이전 STEP 완료 처리
        previous_step_run = self.connection.execute(
            """SELECT step_run_id, step_no FROM step_runs
               WHERE product_run_id = ?
               ORDER BY step_no DESC, step_run_id DESC LIMIT 1""",
            (product_run_id,),
        ).fetchone()

        self._close_previous_steps(product_run_id, current_step)

        # 6. 현재 STEP 실행 레코드 확보
        step_run_id = self._ensure_current_step(product_run_id, current_step)

        # 7. AI/검사 판정 결과 기록 (PASS/FAIL)
        self._record_judgement(
            step_run_id, previous_step_run, current_step,
            event_name, last_result, detail
        )

        # 8. 일시정지(pause_logs) 상태 관리
        self._handle_pause(step_run_id, state)

        # 9. 수동 불량 등록 처리 (해당 시 전체 작업 defect 종료)
        if last_result == "defect":
            self._handle_defect(product_run_id, step_run_id, defect_type, detail)
            return event_id

        # 10. 전체 공정 완료 처리 (해당 시 전체 작업 pass 종료)
        if state == "complete":
            self._handle_complete(product_run_id)

        return event_id

    # ── 내부 단계별 처리 메서드 ──────────────────────────────────────────────

    def _validate_and_normalize(self, state_data: WorkerStateInput) -> tuple:
        """입력 딕셔너리의 필드 유효성을 검사하고 정규화된 튜플을 반환합니다."""
        employee_id = str(state_data.get("employee_id", "")).strip()
        product_id = str(state_data.get("product_id", "")).strip()
        product_name = str(state_data.get("product_name", "")).strip()
        state = str(state_data.get("state", "")).strip().lower()
        last_result = str(state_data.get("last_result", "waiting")).strip().lower()
        event_name = str(state_data.get("event", "")).strip().lower()
        defect_type = str(state_data.get("defect_type", "")).strip().lower()
        detail = str(state_data.get("detail", "")).strip()
        raw_client_event_id = state_data.get("client_event_id")
        client_event_id = None
        if raw_client_event_id is not None:
            if not isinstance(raw_client_event_id, str) or not raw_client_event_id.strip():
                raise ValueError("event_id는 UUID 문자열이어야 합니다.")
            candidate = raw_client_event_id.strip()
            try:
                normalized_event_id = str(uuid.UUID(candidate))
            except (ValueError, AttributeError) as error:
                raise ValueError("event_id는 UUID 문자열이어야 합니다.") from error
            client_event_id = normalized_event_id

        try:
            current_step = int(state_data.get("current_step", 0))
            total_steps = int(state_data.get("total_steps", 0))
        except (TypeError, ValueError) as error:
            raise ValueError("current_step과 total_steps는 정수여야 합니다.") from error

        if not employee_id or not product_id:
            raise ValueError("employee_id와 product_id는 비어 있을 수 없습니다.")
        if state not in {"idle", "running", "paused", "complete"}:
            raise ValueError(f"지원하지 않는 작업 상태입니다: {state}")
        if last_result not in {"waiting", "pass", "fail", "defect"}:
            raise ValueError(f"지원하지 않는 판정 결과입니다: {last_result}")
        if last_result == "defect" and (
            event_name != "manual_defect" or defect_type != "manual"
        ):
            raise ValueError("최종 불량은 manual_defect / manual 정보가 필요합니다.")

        return (
            employee_id, product_id, product_name, state,
            last_result, event_name, defect_type, detail,
            current_step, total_steps, client_event_id,
        )

    def _verify_db_entities(
        self, employee_id: str, product_id: str,
        current_step: int, total_steps: int, state: str
    ) -> sqlite3.Row:
        """작업자 계정, 제품 정보, STEP 범위의 일관성을 검증합니다."""
        employee = self.connection.execute(
            "SELECT role FROM employees WHERE employee_id = ?", (employee_id,)
        ).fetchone()
        if employee is None or employee["role"] != "worker":
            raise ValueError("사용할 수 없는 작업자 계정입니다.")

        product = self.connection.execute(
            "SELECT product_name, total_steps FROM products WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        if product is None:
            raise ValueError(f"등록되지 않은 제품입니다: {product_id}")

        registered_total_steps = int(product["total_steps"])
        if total_steps != registered_total_steps:
            raise ValueError(
                f"전체 STEP 수가 등록 정보와 다릅니다: "
                f"수신 {total_steps}, 등록 {registered_total_steps}"
            )

        minimum_step = 0 if state == "idle" else 1
        if current_step < minimum_step or current_step > total_steps:
            raise ValueError(
                f"current_step은 {minimum_step}~{total_steps} 범위여야 합니다."
            )
        if state == "complete" and current_step != total_steps:
            raise ValueError("완료 상태의 current_step은 마지막 STEP이어야 합니다.")

        return product

    def _record_worker_event(
        self, event_values: tuple, employee_id: str, last_result: str,
        client_event_id: Optional[str],
    ) -> Optional[int]:
        """worker_state_events 테이블에 이벤트를 삽입합니다 (동일 PASS/상태 중복 억제)."""
        if client_event_id is not None:
            existing_event = self.connection.execute(
                """SELECT employee_id, product_id, product_name, state,
                          current_step, total_steps, last_result, event, defect_type, detail
                   FROM worker_state_events
                   WHERE employee_id = ? AND client_event_id = ?""",
                (employee_id, client_event_id),
            ).fetchone()
            if existing_event is not None:
                if tuple(existing_event) != event_values:
                    raise ValueError("같은 event_id에 서로 다른 상태가 포함되어 있습니다.")
                return None
        else:
            latest_event = self.connection.execute(
                """SELECT employee_id, product_id, product_name, state,
                          current_step, total_steps, last_result, event, defect_type, detail
                   FROM worker_state_events
                   WHERE employee_id = ?
                   ORDER BY state_event_id DESC LIMIT 1""",
                (employee_id,),
            ).fetchone()

            if (latest_event is not None and tuple(latest_event) == event_values
                    and last_result != "fail"):
                return None

        cursor = self.connection.execute(
            """INSERT INTO worker_state_events(
                   employee_id, product_id, product_name, state,
                   current_step, total_steps, last_result, event, defect_type,
                   detail, client_event_id, received_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '+9 hours'))""",
            (*event_values, client_event_id),
        )
        return int(cursor.lastrowid)

    def _ensure_product_run(self, employee_id: str, product_id: str) -> int:
        """진행 중인 product_run을 반환하거나 새로 생성합니다."""
        product_run = self.connection.execute(
            """SELECT product_run_id, product_id FROM product_runs
               WHERE employee_id = ? AND completed_at IS NULL
               ORDER BY started_at DESC, product_run_id DESC LIMIT 1""",
            (employee_id,),
        ).fetchone()

        if product_run is not None and str(product_run["product_id"]) != product_id:
            raise ValueError("다른 제품의 미완료 작업이 이미 존재합니다.")

        if product_run is None:
            return int(self.connection.execute(
                """INSERT INTO product_runs(
                       employee_id, product_id, started_at, completed_at
                   ) VALUES (?, ?, datetime('now', '+9 hours'), NULL)""",
                (employee_id, product_id),
            ).lastrowid)
        return int(product_run["product_run_id"])

    def _close_previous_steps(self, product_run_id: int, current_step: int) -> None:
        """현재 STEP보다 이전의 미완료 pause_logs와 step_runs를 종료합니다."""
        self.connection.execute(
            """UPDATE pause_logs SET resumed_at = datetime('now', '+9 hours')
               WHERE resumed_at IS NULL AND step_run_id IN (
                   SELECT step_run_id FROM step_runs
                   WHERE product_run_id = ? AND step_no < ?
               )""",
            (product_run_id, current_step),
        )
        self.connection.execute(
            """UPDATE step_runs SET completed_at = datetime('now', '+9 hours')
               WHERE product_run_id = ? AND step_no < ?
                 AND completed_at IS NULL""",
            (product_run_id, current_step),
        )

    def _ensure_current_step(self, product_run_id: int, current_step: int) -> int:
        """현재 STEP의 step_runs 레코드를 찾아 반환하거나 생성합니다."""
        step_run = self.connection.execute(
            """SELECT step_run_id FROM step_runs
               WHERE product_run_id = ? AND step_no = ?
               ORDER BY step_run_id DESC LIMIT 1""",
            (product_run_id, current_step),
        ).fetchone()

        if step_run is None:
            return int(self.connection.execute(
                """INSERT INTO step_runs(
                       product_run_id, step_no, started_at, completed_at
                   ) VALUES (?, ?, datetime('now', '+9 hours'), NULL)""",
                (product_run_id, current_step),
            ).lastrowid)
        return int(step_run["step_run_id"])

    def _record_judgement(
        self, step_run_id: int, previous_step_run: Optional[sqlite3.Row],
        current_step: int, event_name: str, last_result: str, detail: str
    ) -> None:
        """PASS/FAIL 판정을 올바른 STEP에 연결하여 기록합니다."""
        judgement_result = "pass" if event_name == "step_pass" else last_result
        judgement_step_run_id = step_run_id

        # 직전 STEP 통과 시 넘어온 PASS는 직전 STEP에 바인딩
        if (
            judgement_result == "pass"
            and previous_step_run is not None
            and int(previous_step_run["step_no"]) < current_step
        ):
            judgement_step_run_id = int(previous_step_run["step_run_id"])

        if judgement_result in {"pass", "fail"}:
            self.connection.execute(
                """INSERT INTO judgement_logs(
                       step_run_id, result, source, detail, judged_at
                   ) VALUES (?, ?, ?, ?, datetime('now', '+9 hours'))""",
                (
                    judgement_step_run_id, judgement_result,
                    event_name or "inspection", detail,
                ),
            )

    def _handle_pause(self, step_run_id: int, state: str) -> None:
        """작업 일시정지 상태에 맞춰 pause_logs를 생성하거나 종료합니다."""
        if state == "paused":
            open_pause = self.connection.execute(
                """SELECT pause_id FROM pause_logs
                   WHERE step_run_id = ? AND resumed_at IS NULL LIMIT 1""",
                (step_run_id,),
            ).fetchone()
            if open_pause is None:
                self.connection.execute(
                    """INSERT INTO pause_logs(step_run_id, paused_at, resumed_at)
                       VALUES (?, datetime('now', '+9 hours'), NULL)""",
                    (step_run_id,),
                )
        else:
            self.connection.execute(
                """UPDATE pause_logs SET resumed_at = datetime('now', '+9 hours')
                   WHERE step_run_id = ? AND resumed_at IS NULL""",
                (step_run_id,),
            )

    def _handle_defect(
        self, product_run_id: int, step_run_id: int, defect_type: str, detail: str
    ) -> None:
        """수동 불량 발생 시 진행 중인 pause, step, product_run을 'defect'로 종료합니다."""
        self.connection.execute(
            """UPDATE pause_logs SET resumed_at = datetime('now', '+9 hours')
               WHERE resumed_at IS NULL AND step_run_id IN (
                   SELECT step_run_id FROM step_runs
                   WHERE product_run_id = ?
               )""",
            (product_run_id,),
        )
        self.connection.execute(
            """UPDATE step_runs SET completed_at = datetime('now', '+9 hours')
               WHERE product_run_id = ? AND completed_at IS NULL""",
            (product_run_id,),
        )
        self.connection.execute(
            """INSERT OR IGNORE INTO defect_logs(
                   step_run_id, defect_type, detail, defect_at
               ) VALUES (?, ?, ?, datetime('now', '+9 hours'))""",
            (step_run_id, defect_type, detail),
        )
        self.connection.execute(
            """UPDATE product_runs
               SET completed_at = datetime('now', '+9 hours'), result = 'defect'
               WHERE product_run_id = ? AND completed_at IS NULL""",
            (product_run_id,),
        )

    def _handle_complete(self, product_run_id: int) -> None:
        """공정 완료 시 진행 중인 step과 product_run을 'pass'로 종료합니다."""
        self.connection.execute(
            """UPDATE step_runs SET completed_at = datetime('now', '+9 hours')
               WHERE product_run_id = ? AND completed_at IS NULL""",
            (product_run_id,),
        )
        self.connection.execute(
            """UPDATE product_runs
               SET completed_at = datetime('now', '+9 hours'), result = 'pass'
               WHERE product_run_id = ? AND completed_at IS NULL""",
            (product_run_id,),
        )
