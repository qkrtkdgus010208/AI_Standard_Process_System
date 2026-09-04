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
| `product_dialog.py` | 제품번호·제품명·총 STEP 입력과 검증 |
| `product_detail_dialog.py` | 제품별 STEP 검사 FAIL·불량 버튼 누적 상세표 |
| `worker_account_dialog.py` | 작업자 계정 등록·말소 모달과 입력 검증 |
| `monitoring_gateway.py` | 작업자 인증·Token, 제품 목록, 상태, 로그아웃 JSON/TCP API와 동시 Client 처리 |
| `tcp_client.py` | 로그인 Jetson IP 연결 관리와 관리자 메시지 전송 |
| `theme.py` | 전역 PyQt 테마와 카드 그림자 |
| `sample_data.py`, `mock_tcp_server.py` | 샘플 DB 생성, 포트 5000 수신 확인용 개발 도구 |
| `test_state_persistence.py` | 상태 저장·집계·복원·동적 IP·제품 검증·KST 마이그레이션 회귀 테스트 |

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
  `products`/`get_products`, `state`, `logout`이다.
- `auth` 성공 응답은 미완료 제품 작업이 있으면 제품·현재 STEP·상태·최근 판정을
  `work_state`에 담고, 이어갈 작업이 없으면 `work_state: null`을 반환한다.
- Gateway는 로그인 TCP 연결의 실제 IP를 직원·Token과 메모리에서 연결한다. 관리자 메시지는
  해당 직원의 로그인 Jetson IP:5000으로 전송하며, 로그아웃·재로그인·Gateway 종료 시 연결을
  제거한다. Token 요청은 로그인 때와 동일한 IP에서만 허용한다.
- `auth` 외 요청은 메모리 Token이 필요하고 재시작 시 만료된다. 상태의 직원 정보는
  요청값이 아니라 Token 소유자 정보로 강제한다.
- 미등록 `product_id`는 기록 전에 거부한다. 연속으로 완전히 같은 상태는 중복 저장하지 않는다.
- 계정 말소는 이력을 삭제하지 않고 role과 비밀번호를 폐기하며 열린 출근 기록을 종료한다.
- 직원 상세의 근무시간은 로그인부터 로그아웃까지의 경과시간으로 계산해 점심시간을 포함하며,
  완료된 기록은 9시간 기준으로 정상 근무 또는 시간 미달을 표시한다.
- 다음 STEP은 이전 STEP과 열린 정지를 완료한다. `paused`는 정지를 시작하고 다른 상태는
  정지를 종료한다. `defect` 결과는 불량 완료, `complete` 상태는 정상 완료로 저장한다.
- 주요 DB 관계는 `employees → work_sessions/product_runs`,
  `products → product_runs`, `product_runs → step_runs → pause_logs`이며
  불량은 `step_runs → defect_logs`, 원본 상태는 `worker_state_events`에 저장한다.
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
