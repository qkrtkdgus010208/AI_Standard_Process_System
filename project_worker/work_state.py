"""작업자 화면과 분리된 공정 STEP 상태 제어 모듈입니다."""

from dataclasses import asdict, dataclass

from PyQt5.QtCore import QObject, pyqtSignal


@dataclass
class WorkSnapshot:
    """현재 공정 상태를 UI에 전달하기 위한 데이터입니다."""

    employee_id: str = ""
    employee_name: str = ""
    product_id: str = ""
    product_name: str = ""
    total_steps: int = 1
    current_step: int = 0
    state: str = "idle"
    last_result: str = "waiting"
    event: str = "init"
    defect_type: str = ""
    detail: str = ""


class WorkStateController(QObject):
    """시작·Pause·Reset·PASS/FAIL에 따른 작업 상태를 관리합니다."""

    state_changed = pyqtSignal(dict)
    log_created = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.snapshot = WorkSnapshot()

    def _publish(self) -> None:
        self.state_changed.emit(asdict(self.snapshot))

    def configure(self, employee_id: str, employee_name: str, product_id: str,
                  product_name: str, total_steps: int) -> None:
        """새 작업 정보를 설정하고 대기 상태(0단계)로 초기화합니다."""
        self.snapshot = WorkSnapshot(
            employee_id=employee_id.strip(),
            employee_name=employee_name.strip(),
            product_id=product_id.strip(),
            product_name=product_name.strip(),
            total_steps=max(1, int(total_steps)),
            current_step=0,
            state="idle",
            last_result="waiting",
            event="init",
            defect_type="",
            detail="작업 정보 설정",
        )
        self.log_created.emit("info", "작업 정보가 설정되었습니다 (0단계 대기).")
        self._publish()

    def restore_state(self, employee_id: str, employee_name: str, saved_state: dict) -> None:
        """서버에 남아있는 이전 작업 내용을 복구합니다."""
        product_id = str(saved_state.get("product_id") or "").strip()
        product_name = str(saved_state.get("product_name") or "").strip()
        total_steps = max(1, int(saved_state.get("total_steps") or 1))
        current_step = max(1, min(total_steps, int(saved_state.get("current_step") or 1)))
        state = str(saved_state.get("state") or "running").strip()
        if state not in ("running", "paused"):
            state = "running"
        last_result = str(saved_state.get("last_result") or "waiting").strip()
        defect_type = str(saved_state.get("defect_type") or "").strip()
        detail = str(saved_state.get("detail") or f"STEP {current_step} 이전 작업 복원").strip()

        self.snapshot = WorkSnapshot(
            employee_id=employee_id.strip(),
            employee_name=employee_name.strip(),
            product_id=product_id,
            product_name=product_name,
            total_steps=total_steps,
            current_step=current_step,
            state=state,
            last_result=last_result,
            event="restore",
            defect_type=defect_type,
            detail=detail,
        )
        self.log_created.emit(
            "success",
            f"서버 이전 작업 복원: {product_name} (STEP {current_step}/{total_steps})",
        )
        self._publish()

    def start(self) -> None:
        """설정된 작업을 시작(STEP 1)하거나 Pause 상태에서 재개합니다."""
        if not self.snapshot.employee_id or not self.snapshot.product_id:
            self.log_created.emit("error", "직원번호와 제품번호를 확인하세요.")
            return
        if self.snapshot.state == "paused":
            self.resume()
            return

        self.snapshot.current_step = 1
        self.snapshot.state = "running"
        self.snapshot.last_result = "waiting"
        self.snapshot.event = "start"
        self.snapshot.defect_type = ""
        self.snapshot.detail = "STEP 1 작업 시작"
        self.log_created.emit("success", "STEP 1 작업을 시작했습니다.")
        self._publish()

    def pause(self) -> None:
        """진행 중인 작업을 일시정지합니다."""
        if self.snapshot.state != "running":
            self.log_created.emit("warning", "진행 중인 작업이 아닙니다.")
            return
        self.snapshot.state = "paused"
        self.snapshot.event = "pause"
        self.snapshot.defect_type = ""
        self.snapshot.detail = "작업 일시정지"
        self.log_created.emit("warning", "작업이 일시정지되었습니다.")
        self._publish()

    def resume(self) -> None:
        """Pause된 작업을 재개합니다."""
        if self.snapshot.state != "paused":
            self.log_created.emit("warning", "일시정지된 작업이 아닙니다.")
            return
        self.snapshot.state = "running"
        self.snapshot.event = "resume"
        self.snapshot.defect_type = ""
        self.snapshot.detail = f"STEP {self.snapshot.current_step} 작업 재개"
        self.log_created.emit("info", f"STEP {self.snapshot.current_step} 작업을 재개했습니다.")
        self._publish()

    def register_defect(self) -> None:
        """현재 진행 중인 작업의 수동 불량을 등록(defect 상태 서버 전송)하고 처음(0단계 대기)으로 초기화합니다."""
        if self.snapshot.state != "running" or self.snapshot.current_step <= 0:
            self.log_created.emit("warning", "작업이 진행 중일 때만 불량을 등록할 수 있습니다.")
            return

        # 1. 현재 공정 단계의 수동 불량(defect) 상태를 모니터링 PC로 전송
        self.snapshot.last_result = "defect"
        self.snapshot.event = "manual_defect"
        self.snapshot.defect_type = "manual"
        self.snapshot.detail = f"STEP {self.snapshot.current_step} 작업자 수동 불량 등록"
        self.log_created.emit("error", f"STEP {self.snapshot.current_step} 수동 불량 등록 (서버 전송)")
        self._publish()

        # 2. 작업을 처음(0단계 대기)으로 초기화 후 초기화 상태를 모니터링 PC로 전송
        self.snapshot.current_step = 0
        self.snapshot.state = "idle"
        self.snapshot.last_result = "waiting"
        self.snapshot.event = "init"
        self.snapshot.defect_type = ""
        self.snapshot.detail = "불량 등록 후 초기화"
        self.log_created.emit("info", "불량 등록 후 작업이 처음으로 초기화되었습니다 (0단계 대기).")
        self._publish()

    def reset(self) -> None:
        """현재 작업의 STEP과 판정 상태를 초기화합니다."""
        self.register_defect()

    def apply_judgement(self, result: str, detail: str = "") -> None:
        """AI 또는 UART의 PASS/FAIL 결과를 현재 STEP에 반영합니다."""
        normalized = result.upper()
        if self.snapshot.state != "running":
            self.log_created.emit("warning", "작업 시작 후 판정할 수 있습니다.")
            return
        if normalized not in ("PASS", "FAIL"):
            self.log_created.emit("error", f"알 수 없는 판정값입니다: {result}")
            return
        if normalized == "FAIL":
            self.snapshot.last_result = "fail"
            self.snapshot.event = "ai_fail"
            self.snapshot.defect_type = "ai"
            self.snapshot.detail = detail or f"STEP {self.snapshot.current_step} AI 판정: FAIL"
            self.log_created.emit("error", self.snapshot.detail)
            self._publish()
            return

        completed_step = self.snapshot.current_step
        self.log_created.emit("success", detail or f"STEP {completed_step} 판정: PASS")
        if completed_step >= self.snapshot.total_steps:
            self.snapshot.state = "complete"
            self.snapshot.last_result = "pass"
            self.snapshot.event = "complete"
            self.snapshot.defect_type = ""
            self.snapshot.detail = "전체 조립 공정 완료"
            self.log_created.emit("success", "전체 조립 공정이 완료되었습니다.")
            self._publish()

            # 완료 후 다시 처음(0단계 대기)으로 복귀하여 다시 작업 시작 가능하도록 설정
            self.snapshot.current_step = 0
            self.snapshot.state = "idle"
            self.snapshot.last_result = "waiting"
            self.snapshot.event = "init"
            self.snapshot.defect_type = ""
            self.snapshot.detail = "공정 완료 후 초기화"
            self._publish()
        else:
            self.snapshot.current_step += 1
            self.snapshot.last_result = "waiting"
            self.snapshot.event = "step_pass"
            self.snapshot.defect_type = ""
            self.snapshot.detail = f"STEP {completed_step} 완료 (STEP {self.snapshot.current_step} 진입)"
            self._publish()
