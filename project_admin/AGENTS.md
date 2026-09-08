# Monitoring PC 작업 지침

코드를 수정하거나 진단할 때 이 지도로 탐색 범위를 먼저 좁힌다. 문서와 코드가
다르면 실제 코드가 기준이며, UI에 SQL을 직접 추가하지 않고 DB 작업은
`DatabaseManager` 메서드로 분리한다.

## 파일과 기능 지도

| 파일 | 담당 기능 |
|---|---|
| `main.py` | 실행, DB 초기화, 로그인↔관리자 화면 전환, Gateway 시작·종료 |
| `config.py` | DB 경로, TCP 주소·포트·동시 처리 수·제한시간, 샘플 데이터 설정 |
| `database_manager.py` | 스키마·마이그레이션, 인증, 직원/제품 CRUD, 작업 상태·이력 저장/조회 |
| `login_window.py` | 관리자 로그인 UI와 `verify_admin_login()` 호출 |
| `admin_window.py` | 직원 현황, 제품 관리, 작업자 계정 등록 |
| `employee_detail_dialog.py` | 직원별 로그인/제품/불량/일시정지 이력, STEP 상세 모달 연결, 관리자 메시지 전송 |
| `step_history_dialog.py` | 선택한 제품 작업 회차의 STEP 작업시간 모달 |
| `product_dialog.py` | 제품번호·제품명·총 STEP 및 STEP별 기준 이미지 입력과 검증 |
| `step_guide_storage.py` | 기준 이미지 경로 검증, 1280×720 JPEG 변환·저장·정리 |
| `product_detail_dialog.py` | 제품별 STEP 검사 FAIL·불량 버튼 누적 상세표 |
| `worker_account_dialog.py` | 작업자 계정 등록·말소 모달과 입력 검증 |
| `monitoring_gateway.py` | 작업자 인증·Token, 제품 목록, 상태, 로그아웃 JSON/TCP API와 동시 Client 처리 |
| `tcp_client.py` | 로그인 Jetson IP 연결 관리와 관리자 메시지 전송 |
| `theme.py` | 전역 PyQt 테마와 카드 그림자 |
| `sample_data.py`, `mock_tcp_server.py` | 샘플 DB 생성, 포트 5000 수신 확인용 개발 도구 |
| `test_state_persistence.py` | 상태 저장·집계·복원·동적 IP·제품 검증·KST 마이그레이션 회귀 테스트 |
| `worker_state_recorder.py` | 작업자 상태 검증·중복 판정·제품/STEP/판정/정지/불량 이력의 트랜잭션 저장 |

기능 변경 시 UI 파일과 함께 위 표의 데이터/통신 파일을 확인한다. 특히 상태 처리나
DB 스키마는 `DatabaseManager.record_worker_state()`와 회귀 테스트를 함께 본다.

## 핵심 흐름과 계약

```text
main → LoginWindow/AdminWindow → DatabaseManager → factory.db
Admin/EmployeeDetail → TcpClient → 작업자 PC:5000
작업자 PC → MonitoringGatewayThread:5001 → DatabaseManager
```

- 관리자→작업자는 UTF-8 한 줄
  `MESSAGE|<employee_id>|<UTF-8 URL-safe Base64>`를 전송한다.
- 작업자→관리자는 UTF-8 JSON 한 줄 요청/응답이며 요청 종류는 `auth`,
  `products`/`get_products`, `step_guide`, `state`, `logout`이다. `step_guide`는 현재
  제품·STEP 이미지 한 장을 Base64로 반환하며 작업자는 최대 5MB 응답을 수신한다.
- 새 작업자의 `state` 요청은 논리 이벤트마다 UUID 형식 `event_id`를 보내며 재전송 시
  같은 값을 유지한다. 관리자는 직원번호와 `event_id` 조합으로 중복 집계를 막고,
  `event_id`가 없는 구버전 요청은 기존 중복 판정 방식으로 처리한다.
- `auth` 성공 응답은 미완료 제품 작업이 있으면 제품·현재 STEP·상태·최근 판정을
  `work_state`에 담고, 이어갈 작업이 없으면 `work_state: null`을 반환한다.
- Gateway는 로그인 TCP 연결의 실제 IP를 직원·Token과 메모리에서 연결한다. 관리자 메시지는
  해당 직원의 로그인 Jetson IP:5000으로 전송하며, 로그아웃·재로그인·Gateway 종료 시 연결을
  제거한다. Token 요청은 로그인 때와 동일한 IP에서만 허용한다.
- `auth` 외 요청은 메모리 Token이 필요하고 재시작 시 만료된다. 상태의 직원 정보는
  요청값이 아니라 Token 소유자 정보로 강제한다.
- 미등록 `product_id`는 기록 전에 거부한다. `event_id`가 없는 요청은 연속으로 완전히
  같은 상태를 중복 저장하지 않으며, 같은 `event_id`에 다른 내용이 오면 거부한다.
- 계정 말소는 이력을 삭제하지 않고 role과 비밀번호를 폐기하며 열린 출근 기록을 종료한다.
- 직원 상세의 근무시간은 로그인부터 로그아웃까지의 경과시간으로 계산해 점심시간을 포함하며,
  완료된 기록은 9시간 기준으로 정상 근무 또는 시간 미달을 표시한다.
- 다음 STEP은 이전 STEP과 열린 정지를 완료한다. `paused`는 정지를 시작하고 다른 상태는
  정지를 종료한다. `defect` 결과는 불량 완료, `complete` 상태는 정상 완료로 저장한다.
- STEP 기준 이미지는 `step_guide_images` 폴더에 저장하고 경로·해시·크기는
  `products → product_step_guides`에 저장한다.
- 주요 DB 관계는 `employees → work_sessions/product_runs`,
  `products → product_runs`, `product_runs → step_runs → pause_logs`이며
  불량은 `step_runs → defect_logs`, 원본 상태와 작업자 이벤트 UUID는
  `worker_state_events`에 저장한다.
- 검사 PASS/FAIL은 `step_runs → judgement_logs`에 판정 건별로 저장하고 STEP별 FAIL률을
  집계한다. 작업자의 `event=step_pass`는 `last_result=waiting`이어도 직전 STEP의 PASS로
  저장한다.
  `last_result=pass`와 `state=complete`가 함께 오면 검사 PASS와 정상 완성품을 각각 1건씩
  반영한다. 품질 로그의 직원·제품·STEP 정보는 상위 작업 관계를 조인해 조회한다.
- 품질 초기화는 이력을 삭제하지 않고 `product_quality_baselines`의 ID 기준점 이후만 집계한다.
- 비밀번호는 PBKDF2-SHA256 해시, 시각은 KST 문자열로 저장한다. DB 연결은 foreign key,
  commit/rollback을 유지한다. 동시 읽기·쓰기는 WAL과 열린 상태 중심 복합 인덱스를 사용한다.
- Gateway 상태 신호는 1초 동안 직원번호별로 합쳐 관리자 창에 전달한다. 직원 목록은 한 번의
  DB 조회로 변경된 직원 행만 부분 갱신하며 제품 통계·과거 이력은 수동 새로고침을 유지한다.
- TCP 실패는 UI에서 처리할 수 있도록 `SendResult`로 반환한다.

## 검증과 문서 유지

```powershell
python -m unittest test_state_persistence.py
python main.py
```

DB·상태 저장 변경에는 회귀 테스트를 실행·추가하고, UI 변경은 대상 화면을 실행 확인한다.
모듈 책임, 실행 흐름, DB 스키마 또는 TCP 계약이 바뀌면 이 파일도 갱신한다.

## Agent delegation

The main agent owns:
- interpretation of the user's request and overall task scope
- root-cause and architecture decisions
- database schema and major API/TCP contract decisions
- authentication, authorization, and security decisions
- important business-rule decisions
- new core dependency decisions
- final integration review and completion judgment

Use `luna_worker` for clearly bounded work such as:
- targeted repository investigation
- symbol, reference, import, API, type, and call-path searches
- tracing existing implementation flows
- clearly scoped implementation and localized bug fixes
- repetitive multi-file edits
- tests and targeted validation

Use the file/function map and contracts in this document to narrow the initial search scope.

Search repository-wide when necessary, but do not read every matching file.
Search first, classify results, narrow candidates, then inspect only relevant code.

If the actual code conflicts with this document, treat the code as the current
source of truth and report the discrepancy.

`luna_worker` must not independently:
- redesign project architecture
- change major database schemas
- change authentication or security policy
- change major TCP/API contracts
- invent important business rules
- add a new core dependency
- spawn additional subagents

When such a decision is necessary, return it to the main agent.

The main agent should not repeat broad investigation already completed by
`luna_worker` from the beginning.

Main-agent verification should focus on:
- changed files
- core execution paths
- DB/API/TCP contract consistency
- authentication and security boundaries
- validation results
- uncertainties reported by the worker

Prefer one `luna_worker`.
Use a second worker only for a clearly independent task.
Workers must not edit the same files concurrently.

The main agent makes the final completion judgment.

### Model escalation

The main agent normally handles the task using its current model.

Use `luna_worker` for clearly bounded, repetitive, or execution-heavy work
when delegation is worth the coordination overhead.

Escalate difficult reasoning to `astra_advisor` only when materially stronger
reasoning is likely to improve correctness.

Good reasons to use `astra_advisor` include:
- the root cause remains unclear after normal investigation
- multiple major modules or system boundaries interact in a non-obvious way
- architecture choices or significant tradeoffs must be evaluated
- authentication, authorization, or security behavior may change
- major DB, API, or TCP contracts may need to change
- data integrity or migration safety is at risk
- important business rules conflict or are ambiguous
- a previous reasonable fix failed or caused another regression
- the main agent has substantial uncertainty about the correct solution

Do not use `astra_advisor` for:
- trivial or highly localized changes
- routine CRUD work
- straightforward UI changes
- mechanical multi-file edits
- ordinary test writing or execution
- issues already understood well enough to implement safely

Prefer the cheapest capable path:

1. Main agent handles ordinary work directly.
2. Use `luna_worker` for bounded exploration, implementation, repetition, or validation.
3. Use `astra_advisor` when the remaining difficulty is primarily reasoning,
   ambiguity, risk, or an important technical decision.

Do not escalate merely because a task is large.
Escalate when the hard part is judgment.

After receiving advice from `astra_advisor`, the main agent owns the final
decision, implementation plan, integration review, and completion judgment.
