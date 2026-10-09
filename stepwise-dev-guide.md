# Stepwise 개발 가이드 (Development Prompt Guide)

> Windows용 데이터 기반 매크로 앱 **Stepwise**의 설계 논의 결과를 정리한 개발 기준 문서입니다.
> 이 문서를 AI 개발 도우미(Claude Code 등)에게 컨텍스트로 제공하고, **마일스톤 단위로** 개발을 진행합니다.
> 문서 버전: 1.0 (2026-10-02) / 상태: 설계 확정, 구현 전

---

## 0. 이 문서의 사용법

### 0.1 AI 개발 도우미에게 주는 규칙

1. 구현을 시작하기 전에 이 문서 전체를 읽고, 모호한 부분은 추측하지 말고 질문한다.
2. **한 번에 한 마일스톤(섹션 15)만** 진행한다. 다음 마일스톤의 기능을 미리 만들지 않는다.
3. **범위 밖(섹션 3.4)** 항목은 요청이 없는 한 구현하지 않는다. 기능을 임의로 추가하지 않는다.
4. UI 문자열은 모두 **영어**이며, 코드에 하드코딩하지 않고 `ui/strings.py`에 모은다.
5. 엔진(`engine/`, `services/`)은 UI(`ui/`)를 import하지 않는다. UI가 엔진을 호출하고 시그널로 결과를 받는다.
6. 각 마일스톤 종료 시 **완료 기준(Definition of Done)** 을 하나씩 확인하고 결과를 보고한다.
7. 테스트 가능한 로직(변수 치환, 파일 스키마, 결과 CSV, 이어서 실행)은 반드시 단위 테스트를 함께 작성한다.
8. 사용자는 비개발자 팀원이다. 에러 메시지는 "무슨 일이 일어났고 무엇을 하면 되는지"를 영어 평문으로 쓴다.
9. 이 문서와 구현이 충돌하거나 문서의 결정을 바꿔야 할 이유가 생기면, 코드를 바꾸기 전에 먼저 제안하고 승인을 받는다.

### 0.2 문서 구성

| 섹션 | 내용 |
|---|---|
| 1 | 프로젝트 개요 |
| 2 | 확정된 결정 사항 |
| 3 | 기능 범위 (MVP / 후순위 / 범위 밖) |
| 4 | 기술 스택 |
| 5 | 아키텍처와 폴더 구조 |
| 6 | 매크로 파일 형식 (.swm) |
| 7 | 동작(Action) 명세 |
| 8 | 이미지 인식 명세 |
| 9 | 실행 엔진 명세 (타이밍, Speed, 실패 처리) |
| 10 | 데이터 연동과 결과 CSV, 이어서 실행 |
| 11 | 안전장치와 실행 전 검사 |
| 12 | UI/UX 명세 |
| 13 | 공유와 라이브러리 |
| 14 | 패키징과 배포 |
| 15 | 개발 마일스톤과 단계별 프롬프트 |
| 16 | 테스트 전략 |
| 17 | 알려진 함정 체크리스트 |
| 18 | 미결정 항목 |
| 부록 | 용어집, 예시 파일 |

---

## 1. 프로젝트 개요

### 1.1 목적

사내 시스템(SAP/ERP, 웹, 사내 전용 프로그램)에 **반복적으로 클릭하고 입력하는 작업**을 자동화한다.
특히 **Excel/CSV 데이터 표의 각 행을 기준으로** "클릭 → 1열 값 입력 → 다른 곳 클릭 → 2열 값 입력 → 이미지 클릭 → 3열 값 입력 …"을 수십~수백 행 반복하는 용도다.

### 1.2 핵심 사용 시나리오

1. **일반(단순) 매크로**: 좌표 클릭, 텍스트 입력, 키 입력, 대기, 이미지가 나타날 때까지 대기, 이미지 클릭을 순서대로 실행한다.
2. **데이터 매크로**: 데이터 파일을 연결하면 같은 동작 목록을 데이터 행마다 반복 실행한다. 값은 `{열이름}` 변수로 입력한다.
3. **이어서 실행**: 중간에 멈춘 경우, 데이터 표의 상태 표시를 보고 멈춘 행부터 다시 실행한다.
4. **공유**: 팀원끼리 매크로 파일(.swm)을 공유 폴더로 주고받는다. 화면 해상도가 다르면 경고한다.

### 1.3 사용자와 환경

| 항목 | 내용 |
|---|---|
| 사용자 | 팀원들 (비개발자). 단순함과 안전장치가 최우선 |
| 실행 환경 | **Azure 클라우드 PC 안에서 직접 실행** (원격 화면을 외부에서 조작하지 않음) |
| 원격 접속 방식 | 아직 미확인 (RDP / Azure Virtual Desktop / 웹 클라이언트 등) → M0에서 검증 |
| OS | Windows 10/11 (클라우드 PC 기준) |
| UI 언어 | 영어 |
| 처리 규모 | 한 번에 수십~수백 행 (수천 행은 고려하지 않음) |
| 설치 | `Setup.exe` 설치형. Python 내장. **사용자 폴더 설치, 관리자 권한 불필요** (IT 정책상 허용 확인됨) |
| 입력 데이터 언어 | 한국어, 영어, 폴란드어 등 혼용 가능 (유니코드 입력 필수) |

### 1.4 앱 이름

**Stepwise** (임시 확정). 매크로 파일 확장자는 `.swm` (Stepwise Macro).

### 1.5 설계 철학

- **위에서 아래로 읽히는 목록**이 곧 매크로다. 플로우차트나 노드 UI는 만들지 않는다.
- **기본은 좌표 기반**, 중요한 지점에만 **이미지 확인(Guard/Verify)** 을 붙인다.
- **실패하면 멈춘다.** 추측해서 계속 진행하지 않는다. 이중 입력 사고를 막는 것이 속도보다 중요하다.
- **성공 여부를 알 수 있어야 한다.** Verify 이미지가 없는 핵심 동작은 경고한다.
- 하나의 구조(3구역)로 단순 매크로와 데이터 매크로를 모두 처리한다.

---

## 2. 확정된 결정 사항

| # | 항목 | 결정 |
|---|---|---|
| 1 | 실행 방식 | 클라우드 PC 안에서 직접 실행 |
| 2 | 언어/UI | Python 3.12 + PySide6 |
| 3 | 배포 | PyInstaller + Inno Setup, 사용자 폴더 설치 |
| 4 | 매크로 구조 | **Setup / Per Row / Cleanup** 3구역 고정. 데이터 미연결 시 Per Row는 1회 실행 |
| 5 | 매크로 관리 | 왼쪽 라이브러리 패널에서 여러 매크로 관리 (폴더 기반) |
| 6 | 파일 형식 | 매크로 1개 = `.swm` 패키지 1개 (zip: JSON + 이미지) |
| 7 | 기본 동작 방식 | 좌표 기반 + 선택적 이미지 Guard/Verify |
| 8 | 이미지 못 찾을 때 | 설정한 timeout(예: 10초) 동안 반복 검색 → 못 찾으면 **즉시 중지** |
| 9 | 이미지 발견 후 | 설정한 시간(After found, 예: 3초) 추가 대기 후 다음 단계 |
| 10 | 실패 시 | **중지 + 로그 + 스크린샷 저장**. 자동 재시도/건너뛰기 없음 |
| 11 | 녹화 기능 | **제외**. 대신 캡처 도우미(F8 좌표 / F9 영역 이미지) |
| 12 | 이어서 실행 | MVP 포함. 데이터 표에 Status 열 표시 |
| 13 | 결과 기록 | 원본 데이터 파일은 수정하지 않고 **별도 결과 CSV**에 기록 |
| 14 | 비상 정지 | 기본 **F12**, 설정에서 변경 가능 |
| 15 | 이미지 정확도 | 기본 **엄격(Strict)**, 고급 설정에서 조절 |
| 16 | 지연 시간 | **동작별 개별 설정**. 기본값 **0.2초** |
| 17 | **Speed 전체 지연** | 실행 전 확인 화면에서 **Normal / Slow(+0.5s) / Very slow(+1s)** 선택 (섹션 9.3) |
| 18 | 실행 중 UI | 메인 창이 **작은 플로팅 패널**로 축소 |
| 19 | 해상도 | 앱 시작 시 해상도/배율 인식 후 상태바에 표시. 매크로에 기록. 불일치 시 경고 |
| 20 | 스텝이 많을 때 | 구역 접기, 그룹(1단계), Note 열, 검색/필터, 자동 스크롤, 조밀 보기 |
| 21 | 편의 기능 | Undo/Redo, Test this step, Show on screen, Test match, 자동 저장/복구 |

---

## 3. 기능 범위

### 3.1 MVP (반드시 구현)

**동작**
- Click (좌표, 좌/우/가운데 버튼, 1~2회 클릭)
- Click image (이미지를 찾아 클릭, 오프셋 지원)
- Type text (고정 텍스트 + `{열이름}` 변수, 붙여넣기/키 입력 두 가지 방식)
- Key press (Enter, Tab, Ctrl+S 등 단일 키 또는 조합, 반복 횟수)
- Wait (고정 시간)
- Wait for image (나타날 때까지, timeout, After found 지연, 안정화 옵션)
- Wait until image disappears (사라질 때까지)
- Group (1단계, 접기/펼치기)

**동작 공통 옵션**
- Enabled 토글, Note(메모), Wait before(동작별 지연)
- Guard 이미지 (실행 전 확인), Verify 이미지 (실행 후 확인)

**데이터**
- Excel(.xlsx), CSV 불러오기, 시트 선택, 헤더 행
- `{열이름}` 변수, 입력 시 열 이름 자동완성
- 데이터 미리보기 표 + **Status 열**
- 시작 행 지정, 이어서 실행, 결과 CSV 기록

**실행**
- Run / Pause / Stop, Step-by-step 모드, Run 1 row (첫 대상 행만 테스트)
- Speed 선택 (Normal / Slow / Very slow)
- 실행 전 확인 화면(검사 결과, 시작 행, 카운트다운)
- 실행 중 플로팅 패널
- 실패 시 중지, 로그, 실패 시점 스크린샷, 해당 줄 강조
- 실행 종료 요약 화면

**안전장치**
- F12 비상 정지 (변경 가능)
- 해상도/DPI 불일치 경고
- 실행 전 검사(Pre-flight)
- 시작 카운트다운
- 실행 중 화면 절전/화면 보호기 방지

**편의 기능**
- 캡처 도우미 (F8: 현재 마우스 좌표를 Click으로 추가 / F9: 화면 영역을 이미지로 저장)
- Pick 버튼, Show on screen(좌표 시각화), Test this step, Test match(일치율 표시)
- Undo / Redo
- 자동 저장과 비정상 종료 후 복구
- 매크로 라이브러리(폴더 기반), 검색, `.swm` 저장/불러오기, 편집 잠금
- 실행 로그 보관

### 3.2 있으면 좋음 (후순위, MVP 이후)

- 매크로 변수 확장: `{Today}`, `{RowNumber}` 등 내장 변수
- 동작 템플릿/스니펫 라이브러리 (예: "SAP 로그인 3단계")
- 도움말 툴팁, 첫 실행 가이드
- 그룹 중첩
- 사용자 정의 Speed 값
- 로그 보관 기간 설정, 로그 화면 필터 고도화
- 실행 중 마우스를 크게 움직이면 자동 일시정지

### 3.3 나중에 (로드맵)

- SAP GUI Scripting 플러그인 (IT가 서버/클라이언트 설정을 허용한 경우)
- Playwright 기반 웹 플러그인
- 스케줄 실행
- 멀티 모니터 고급 처리
- 매크로 공유 라이브러리 고도화 (버전 관리 등)
- 조건 분기(if/else)

### 3.4 범위 밖 (만들지 않는다)

| 항목 | 이유 |
|---|---|
| 마우스/키보드 **녹화** | 재생이 그대로 안 되는 경우가 많고 수정 비용이 큼. 캡처 도우미로 대체 |
| 노드/플로우차트 UI | 동작이 많아지면 오히려 복잡. 목록 방식 유지 |
| 조건 분기, 중첩 반복 | 1차 버전 제외 (필요가 확인되면 추가) |
| 실패 시 자동 재시도/자동 건너뛰기 | 이중 입력 위험. 실패는 항상 중지 |
| OCR, AI 기반 화면 인식 | 복잡도 대비 가치 낮음 |
| 비밀번호/자격 증명 저장 | 보안 위험. 매크로에 비밀번호를 넣지 않도록 안내 |
| 클라우드 동기화, 자동 업데이트 | 설치 파일 재배포로 대체 |
| 외부 스크립트(Python 등) 실행 동작 | 보안과 단순성 |

---

## 4. 기술 스택

| 영역 | 선택 | 비고 |
|---|---|---|
| 언어 | Python 3.12 (64-bit) | |
| UI | PySide6 (Qt 6) | 표/트리 뷰, 드래그 정렬, 하이라이트, 플로팅 창 |
| 마우스/키보드 입력 | Windows `SendInput` (ctypes) | 안정적, 의존성 적음 |
| 화면 캡처 | `mss` | 영역 캡처 빠름 |
| 이미지 인식 | `opencv-python-headless` + `numpy` | `cv2.matchTemplate` (TM_CCOEFF_NORMED) |
| Excel | `openpyxl` (`read_only=True`, `data_only=True`) | pandas는 설치 파일이 커져서 사용하지 않음 |
| CSV | 표준 `csv` + 인코딩 감지(`charset-normalizer`) | 구분자/인코딩 자동 감지 |
| 클립보드 | ctypes 또는 `pywin32` (M0에서 안정적인 쪽 선택) | 엔진 스레드에서 사용 가능해야 함 |
| 전역 단축키 | Win32 `RegisterHotKey` (ctypes) | 관리자 권한 불필요 |
| 화면 절전 방지 | `SetThreadExecutionState` | 실행 중에만 |
| 파일 형식 | JSON + zip (`.swm`) | 표준 `json`, `zipfile` |
| 테스트 | `pytest`, 필요 시 `pytest-qt` | |
| 정적 검사 | `ruff`, (선택) `mypy` | |
| 패키징 | PyInstaller (**onedir**) + Inno Setup | onefile보다 시작 속도, 백신 오탐 측면에서 유리 |

개발 규칙
- 가상환경(venv) 사용, `requirements.txt`는 버전을 고정(pin)한다.
- 타입 힌트를 사용하고, 데이터 모델은 `dataclasses` 또는 `pydantic` 없이 표준 dataclass로 구현한다(의존성 최소화).
- 로깅은 표준 `logging` 모듈, 파일 로테이션 적용.

---

## 5. 아키텍처와 폴더 구조

### 5.1 4개 층

```
┌─────────────────────────────────────────────┐
│ UI (PySide6)                                │  표시, 편집, 사용자 입력
├─────────────────────────────────────────────┤
│ Macro Model (core/)                         │  동작 목록, 스키마, 파일 입출력, 변수 치환
├─────────────────────────────────────────────┤
│ Execution Engine (engine/)                  │  실행 흐름, 타이밍, 실패 처리, 결과 기록
├─────────────────────────────────────────────┤
│ Services (services/)                        │  입력, 화면 캡처, 이미지 매칭, 데이터, 단축키
└─────────────────────────────────────────────┘
```

### 5.2 스레드 모델

- **UI 스레드**: Qt 이벤트 루프. 화면 갱신만 담당한다.
- **엔진 스레드**: 매크로 실행. 모든 대기는 `threading.Event.wait(timeout)` 기반으로 **즉시 중단 가능**해야 한다(`time.sleep` 직접 사용 금지).
- 엔진은 Qt 시그널(또는 콜백 인터페이스)로 이벤트를 UI에 전달한다.
  - `run_started`, `row_started(row)`, `step_started(step_id)`, `step_finished(step_id)`, `row_finished(row, status)`, `run_finished(summary)`, `run_failed(failure)`
- Pause는 **동작 사이**에서만 적용한다. Stop/F12는 다음 체크포인트(대기 중 포함)에서 즉시 중단한다.

### 5.3 폴더 구조

```
stepwise/
├─ pyproject.toml
├─ requirements.txt
├─ requirements-dev.txt
├─ src/stepwise/
│  ├─ __main__.py
│  ├─ app.py                    # 앱 시작, DPI 설정, 설정 로드
│  ├─ core/
│  │  ├─ models.py              # Macro, Section, Group, Action 등 dataclass
│  │  ├─ schema.py              # JSON 검증, schema_version
│  │  ├─ migration.py           # 구버전 파일 변환
│  │  ├─ package.py             # .swm(zip) 읽기/쓰기
│  │  └─ variables.py           # {열이름} 파싱, 치환, 이스케이프
│  ├─ engine/
│  │  ├─ runner.py              # 실행 루프 (구역/행/동작)
│  │  ├─ actions.py             # 동작 타입별 실행 구현
│  │  ├─ timing.py              # wait_before + Speed 계산, 중단 가능한 sleep
│  │  ├─ preflight.py           # 실행 전 검사
│  │  ├─ results.py             # 결과 CSV 기록/복원
│  │  └─ errors.py              # StepFailure, AbortRequested 등
│  ├─ services/
│  │  ├─ input_win.py           # SendInput: 마우스/키보드/유니코드 입력
│  │  ├─ clipboard.py           # 클립보드 저장/복원/붙여넣기
│  │  ├─ screen.py              # 캡처, 해상도/DPI 조회, 블랙 화면 감지
│  │  ├─ matcher.py             # 템플릿 매칭
│  │  ├─ hotkeys.py             # RegisterHotKey
│  │  ├─ data_source.py         # xlsx/csv 읽기
│  │  ├─ lock.py                # 매크로 편집 잠금
│  │  └─ power.py               # 절전/화면보호기 방지
│  ├─ ui/
│  │  ├─ main_window.py
│  │  ├─ macro_library.py
│  │  ├─ action_tree.py         # 동작 목록 (모델/뷰/델리게이트)
│  │  ├─ properties_panel.py
│  │  ├─ data_panel.py
│  │  ├─ preflight_dialog.py
│  │  ├─ run_panel.py           # 플로팅 패널
│  │  ├─ run_summary.py
│  │  ├─ settings_dialog.py
│  │  ├─ capture_overlay.py     # F8/F9/Pick 오버레이
│  │  ├─ strings.py             # 모든 UI 문자열(영어)
│  │  └─ styles.qss
│  └─ resources/                # 아이콘 등
├─ tests/
├─ tools/
│  ├─ spike/                    # M0 검증 스크립트
│  └─ dummy_erp.py              # E2E 테스트용 가짜 입력 폼 앱
├─ installer/
│  ├─ stepwise.spec             # PyInstaller
│  ├─ setup.iss                 # Canonical Inno Setup definition
│  └─ stepwise.iss              # Compatibility include wrapper
└─ docs/
```

### 5.4 로컬 저장 위치

| 용도 | 위치 |
|---|---|
| 앱 설정 | `%APPDATA%\Stepwise\settings.json` |
| 자동 저장/복구 | `%APPDATA%\Stepwise\recovery\` |
| 로그 | `%LOCALAPPDATA%\Stepwise\logs\` |
| 기본 매크로 라이브러리 폴더 | `%USERPROFILE%\Documents\Stepwise\Macros` (설정에서 변경, 공유 폴더 지정 가능) |
| 기본 결과 폴더 | `%USERPROFILE%\Documents\Stepwise\Results` (설정에서 변경) |

---

## 6. 매크로 파일 형식 (.swm)

### 6.1 패키지 구조

`.swm`은 zip 파일이다.

```
InvoiceEntry.swm
├─ macro.json          # 매크로 정의
├─ images/
│  ├─ img_3f2a....png  # Guard/Verify/Click image에 쓰이는 이미지
│  └─ ...
└─ thumbnail.png       # (선택) 라이브러리 목록용
```

규칙
- 이미지는 **패키지 안에 포함**한다 (파일 하나만 전달해도 이미지가 빠지지 않도록).
- **데이터 파일은 패키지에 포함하지 않는다** (업무 데이터 유출 방지). `data_source`에는 파일 이름 힌트와 설정만 저장한다.
- `schema_version` 필드를 반드시 두고, 새 버전 앱은 구버전 파일을 `migration.py`로 변환해서 연다. 새 버전 파일을 구버전 앱이 열면 "Please update Stepwise" 오류를 표시한다.
- 저장은 **임시 파일에 쓴 뒤 교체(atomic write)** 하여 저장 중 중단되어도 기존 파일이 깨지지 않게 한다.

### 6.2 macro.json 필드

| 필드 | 설명 |
|---|---|
| `schema_version` | 정수. 현재 `1` |
| `id` | UUID |
| `name`, `description` | 표시 이름, 설명 |
| `created_by`, `created_at`, `modified_at` | 메타 정보 |
| `recorded_screen` | 저장 시점의 화면 정보: `width`, `height`, `scale_percent`, `monitor_count` |
| `settings` | 매크로 단위 기본값: `default_wait_before`(기본 0.2), `image_confidence`(기본 0.95), `poll_interval`(기본 0.25), `type_mode`(기본 `paste`) |
| `data_source` | `null` 또는 `{type, file_hint, sheet, header_row, encoding, delimiter}` |
| `setup` | 처음 한 번만 실행되는 항목 배열 |
| `per_row` | 데이터 행마다 실행되는 항목 배열 (데이터 없으면 1회) |
| `cleanup` | 마지막에 한 번 실행되는 항목 배열 |

각 구역 배열의 요소는 **동작(Action)** 또는 **그룹(Group)** 이다. 그룹은 1단계만 허용하며 그룹 안에는 동작만 들어간다.

### 6.3 동작 공통 필드

| 필드 | 설명 |
|---|---|
| `id` | UUID (실행 로그/실패 위치 표시에 사용) |
| `type` | `click`, `click_image`, `type_text`, `key`, `wait`, `wait_image`, `wait_image_gone`, `group` |
| `enabled` | `true/false` |
| `note` | 사용자 메모 (문자열, 선택) |
| `wait_before` | 초. `null`이면 매크로 기본값(`settings.default_wait_before`) 사용 |
| `guard` | (선택) 실행 전 확인 이미지 조건 (이미지 동작 제외) |
| `verify` | (선택) 실행 후 확인 이미지 조건 (이미지 동작 제외) |

Guard/Verify 객체
```json
{ "image": "images/form_open.png", "region": null, "confidence": null, "timeout": 10, "after_found": 0 }
```
- `region`: `null`(전체 화면) 또는 `[x, y, w, h]`
- `confidence`: `null`이면 매크로 기본값 사용
- `timeout`: 초. 이 시간 안에 못 찾으면 실패(중지)
- `after_found`: 찾은 뒤 추가 대기(초)

### 6.4 예시

부록 A에 전체 예시가 있다.

---

## 7. 동작(Action) 명세

모든 좌표는 **물리 픽셀 기준 절대 화면 좌표**다 (DPI 배율이 적용되기 전의 실제 픽셀). MVP는 **기본(Primary) 모니터만** 지원하고, 모니터가 2개 이상이면 경고한다.

### 7.1 Click

| 파라미터 | 설명 |
|---|---|
| `x`, `y` | 클릭 좌표 |
| `button` | `left`(기본) / `right` / `middle` |
| `clicks` | `1`(기본) / `2` (더블클릭) |

동작: 마우스를 좌표로 이동 → 짧은 안정화 지연(약 30~50ms) → 클릭.

### 7.2 Click image

| 파라미터 | 설명 |
|---|---|
| `image` | 이미지 파일 경로(패키지 내) |
| `region` | 검색 영역 (`null` = 전체 화면) |
| `confidence` | 일치율 임계값 (`null` = 매크로 기본값) |
| `timeout` | 못 찾으면 실패하기까지의 시간(초, 기본 10) |
| `offset_x`, `offset_y` | 찾은 이미지 **중심**에서의 상대 위치로 클릭 (기본 0, 0) |
| `button`, `clicks` | Click과 동일 |
| `after_found` | 클릭 전 추가 대기(초, 기본 0) |

오프셋을 쓰면 "이 라벨 오른쪽 120px 지점 클릭"처럼 창 위치가 달라져도 동작하는 **상대 좌표 클릭**이 된다.

### 7.3 Type text

| 파라미터 | 설명 |
|---|---|
| `text` | 입력할 문자열. `{열이름}` 변수 사용 가능 |
| `mode` | `paste`(기본, 클립보드 붙여넣기) / `keystrokes`(유니코드 키 입력) |
| `select_all_first` | `true`면 입력 전 Ctrl+A (기본 `false`) |

- `paste`: 기존 클립보드 내용을 저장 → 텍스트를 클립보드에 넣음 → Ctrl+V → 짧은 대기 → 클립보드 복원.
  IME 문제 없이 한글/폴란드어 등을 입력할 수 있다.
- `keystrokes`: `SendInput`의 `KEYEVENTF_UNICODE`로 문자를 하나씩 입력.
  **원격 환경에서 클립보드 리디렉션이 정책으로 막혀 있을 수 있으므로** 대체 수단으로 반드시 제공한다 (M0에서 어느 쪽이 되는지 검증).
- 치환 결과가 빈 문자열이면 사전 검사에서 경고한다(섹션 11.2).

### 7.4 Key press

| 파라미터 | 설명 |
|---|---|
| `keys` | `enter`, `tab`, `esc`, `f2`, `ctrl+s`, `alt+f4`, `ctrl+shift+end` 등 |
| `repeat` | 반복 횟수 (기본 1) |

- 키 이름 목록은 `input_win.py`에 정의하고, UI에서는 드롭다운 + "직접 누르기(Press keys…)" 입력 방식을 제공한다.
- 조합 키는 눌렀다 떼는 순서(누르기 순방향, 떼기 역방향)를 지킨다.

### 7.5 Wait

| 파라미터 | 설명 |
|---|---|
| `seconds` | 대기 시간 |

Speed 설정의 영향을 받지 않는다 (명시적으로 지정한 대기이므로).

### 7.6 Wait for image

| 파라미터 | 설명 |
|---|---|
| `image`, `region`, `confidence` | 이미지 조건 |
| `timeout` | 최대 대기 시간. 못 찾으면 **실패(중지)** |
| `after_found` | 찾은 뒤 추가 대기 (예: 3초) |
| `stable_for` | (고급) 이미지가 이 시간 동안 **계속** 보여야 인정 (기본 0 = 꺼짐, 예: 0.5) |

예) `timeout 10s / after_found 3s`: 이미지가 2초에 나타나면 5초째에 다음 단계 실행.

### 7.7 Wait until image disappears

| 파라미터 | 설명 |
|---|---|
| `image`, `region`, `confidence` | 이미지 조건 |
| `timeout` | 사라지기까지 최대 대기. 안 사라지면 **실패(중지)** |
| `appear_grace` | 이미지가 처음에 나타나길 기다리는 시간 (기본 0). 로딩 스피너가 약간 늦게 뜨는 경우용 |
| `after_gone` | 사라진 뒤 추가 대기 |

- 시작 시점에 이미지가 없고 `appear_grace`가 0이면 즉시 성공으로 간주한다.
- SAP/웹의 "처리 중" 표시가 사라질 때까지 기다리는 용도.

### 7.8 Group

| 파라미터 | 설명 |
|---|---|
| `name` | 그룹 이름 (예: "Fill vendor info") |
| `collapsed` | 접힘 상태 (UI 상태, 저장됨) |
| `items` | 안에 포함된 동작들 |

- 그룹 자체는 실행 로직이 없고 **표시/정리용 컨테이너**다. Enabled를 끄면 안의 모든 동작이 건너뛰어진다.
- 그룹 안에 그룹을 넣을 수 없다 (MVP).

### 7.9 Guard / Verify (동작 공통 옵션)

- **Guard**: 동작 실행 **전에** 이미지가 보이는지 확인한다. (예: 입력 폼이 열려 있어야 클릭 진행)
- **Verify**: 동작 실행 **후에** 이미지가 나타나는지 확인한다. (예: 저장 클릭 후 "Saved" 문구 확인)
- 둘 다 timeout 내에 못 찾으면 **실패(중지)** 한다.
- 이미지 동작(Click image, Wait for image, Wait until image disappears)에는 Guard/Verify를 붙이지 않는다 (이미 이미지 조건이 있으므로).

---

## 8. 이미지 인식 명세

### 8.1 매칭 방식

- 화면 캡처(`mss`) → 그레이스케일 변환(기본, 옵션으로 컬러) → `cv2.matchTemplate(..., TM_CCOEFF_NORMED)` → 최대 일치율과 위치를 구한다.
- 일치율 ≥ `confidence`이면 "찾음".
- **스케일 변환(멀티스케일) 매칭은 하지 않는다.** 해상도/배율이 다르면 일치하지 않는 것이 정상이며, 이는 해상도 불일치 경고로 사용자에게 알린다.
- 검색 영역(`region`)이 지정되면 해당 영역만 캡처하고 매칭하여 속도와 오탐을 줄인다.

### 8.2 정확도(Confidence)

| 프리셋 | 값 | 비고 |
|---|---|---|
| **Strict (기본)** | **0.95** | 오클릭 방지 우선 |
| Normal | 0.90 | |
| Loose | 0.85 | |
| Custom | 0.80 ~ 0.99 | 고급 설정에서 슬라이더 |

- 앱 설정(고급)에서 기본 프리셋을 바꿀 수 있고, 매크로 단위(`settings.image_confidence`), 동작 단위(`confidence`)로 덮어쓸 수 있다.
- 우선순위: **동작 값 > 매크로 값 > 앱 기본값**.

### 8.3 폴링

- 이미지를 찾을 때까지 `poll_interval`(기본 0.25초)마다 재검색한다.
- 매 반복에서 중지 요청(F12/Stop)을 확인한다.
- 화면 캡처가 실패하거나 **전체가 단색(블랙)** 인 경우 "Screen unavailable (session locked or disconnected?)"로 즉시 실패 처리한다.

### 8.4 검색 영역 지정 UI

- 기본: **Full screen**.
- 빠른 버튼: **Around capture position (±100 px)** — 이미지를 캡처한 위치 주변만 검색.
- Custom: 화면에서 드래그로 지정(오버레이).
- 이미지를 캡처할 때(F9) 캡처 위치를 `capture_rect`로 함께 저장해서 위 빠른 버튼에 사용한다.

### 8.5 Test match

- 속성 패널의 **[Test match]** 버튼: 현재 화면에서 매칭을 한 번 실행하고
  - 최고 일치율(%), 위치, 임계값 통과 여부를 표시한다.
  - 일치 위치를 화면에 사각형으로 잠깐 표시한다.
  - **임계값 미달이어도 최고 일치율과 위치를 보여준다** (정확도를 감이 아니라 수치로 조정하게 하기 위함).

### 8.6 이미지 저장

- PNG 저장, 파일명은 `img_<짧은uuid>.png`, 목록에서는 사용자가 붙인 label을 표시한다.
- 캡처 시점의 화면 배율(`scale_percent`)을 메타 정보로 함께 저장한다 (진단용).

---

## 9. 실행 엔진 명세

### 9.1 실행 순서 (전체)

```
[사전 검사] → [카운트다운] → [Setup 1회] → [Per Row: 행 1..N 반복] → [Cleanup 1회] → [요약]
```

- 데이터가 연결되지 않은 경우 **Per Row는 1회만** 실행된다. (단순 매크로로 동작)
- 사전 검사 옵션(실행 확인 화면): `Skip Setup`(이미 로그인된 상태 등), `Skip Cleanup`.
- **Run 1 row**: Setup → 첫 대상 행 1개 실행 후 멈춘다 (Cleanup 미실행). 이후 전체 실행 시 `Skip Setup`을 선택할 수 있다.
- 비활성(`enabled=false`) 동작과 그룹은 건너뛴다.
- 실패한 경우 **Cleanup은 자동 실행하지 않는다** (화면 상태를 알 수 없으므로). 미결정 항목 18-1 참고.

### 9.2 한 동작의 실행 순서

```
1. wait_before + speed_extra  (중단 가능한 대기)
2. Guard 있으면: timeout 동안 폴링 → 못 찾으면 실패(중지)
                  찾으면 guard.after_found 만큼 대기
3. 동작 실행
4. Verify 있으면: timeout 동안 폴링 → 못 찾으면 실패(중지)
                  찾으면 verify.after_found 만큼 대기
```

- "wait after"는 별도로 두지 않는다. 다음 동작의 `wait_before`와 이미지 조건의 `after_found`로 충분하며, 항목이 늘어나 헷갈리는 것을 막기 위함이다.
- 이미지 동작은 자체 `timeout`/`after_found`를 가진다.

### 9.3 지연 시간과 Speed 설정 (확정)

**동작별 지연**
- 각 동작은 `wait_before`(초)를 개별 설정할 수 있다.
- `null`이면 매크로 기본값 `settings.default_wait_before`를 쓰며, **기본값은 0.2초**다.
- 매크로 기본값의 초기값은 앱 설정의 "Default wait before"(기본 0.2)에서 복사된다. 한 번 매크로가 만들어진 뒤에는 매크로 파일에 저장된 값을 사용한다(공유 시 동일하게 동작).

**Speed (전체 지연 추가)**

실행 확인 화면(Run 클릭 시)에서 선택한다.

| 선택지 | 추가 지연(`speed_extra`) |
|---|---|
| **Normal** (기본) | +0 s |
| Slow | +0.5 s |
| Very slow | +1.0 s |

적용 규칙
- 실제 대기 = `(step.wait_before 또는 매크로 기본값) + speed_extra`
- `speed_extra`는 **실행되는 모든 동작의 wait_before에 더해진다** (그룹 안의 동작 포함).
- **적용하지 않는 것**: 이미지 `timeout`, `after_found`, `after_gone`, `stable_for`, Wait 동작의 `seconds`, 클릭 사이 내부 안정화 지연.
- Speed는 **매크로 파일에 저장하지 않는다**(실행 시점의 선택). 마지막에 선택한 값만 앱 설정에 기억해 다음 실행 때 기본으로 보여준다.
- 용도: ERP 응답이 느린 날 매크로를 수정하지 않고 전체를 한 번에 늦추기.
- 실행 중 플로팅 패널에 현재 Speed를 표시한다 (예: `Speed: Slow +0.5s`).

### 9.4 실패 처리 (중지 원칙)

| 실패 유형 | 예시 | 처리 |
|---|---|---|
| 이미지 timeout | Guard/Verify/Wait image가 시간 안에 안 나타남(또는 안 사라짐) | **즉시 중지** |
| 화면 사용 불가 | 캡처 실패, 블랙 화면(세션 잠김/끊김) | 즉시 중지 |
| 데이터 문제 | 변수 열 없음, 값 비어 있음 | **실행 전 검사로 사전 차단** |
| 환경 문제 | 해상도 불일치, 이미지 파일 누락 | **실행 전 검사로 사전 경고/차단** |
| 사용자 중단 | F12, Stop 버튼 | 즉시 중지, 해당 행은 `Interrupted` |
| 입력 씹힘 | 클릭했는데 화면이 안 바뀜 | **Verify가 있어야만 감지 가능** → 사전 검사에서 Verify 부재 경고 |
| 예기치 않은 예외 | 코드 오류 등 | 중지, 로그에 스택 트레이스, 사용자에게는 평문 메시지 |

실패 시 항상 수행:
1. 실행 즉시 중단
2. **전체 화면 스크린샷**을 결과 폴더의 `screenshots/`에 저장 (파일명: `<run_id>_row<N>_step<id>.png`)
3. 결과 CSV에 행 상태(`Failed` 또는 `Interrupted`), 실패 단계, 사유 기록
4. 메인 창을 복원하고 **실패한 줄을 강조 표시**, 플로팅 패널에 사유 표시
5. 실행 요약 화면 표시

실패 메시지 형식 예: `Row 37, step 5 "Click image: save.png" — image not found within 10 s (best match 71%).`

### 9.5 일시정지와 단계 실행

- **Pause**: 현재 동작이 끝난 뒤 멈춘다. Resume 가능.
- **Step-by-step 모드**: 매 동작 **실행 직전**에 멈추고 `Next` 버튼(또는 단축키)을 눌러야 진행한다. 새 매크로 테스트용.
- **Test this step**: 편집 화면에서 선택한 동작 1개만 실행 (카운트다운 후, Guard/Verify 포함, 데이터 변수는 선택한 샘플 행 사용).

---

## 10. 데이터 연동, 결과 CSV, 이어서 실행

### 10.1 데이터 읽기

- 지원: `.xlsx`, `.csv`.
- **xlsx**: 시트 선택, 헤더 행 번호 지정(기본 1행), `data_only=True`(수식은 저장된 계산 값 사용).
- **csv**: 인코딩 자동 감지(`utf-8-sig`, `utf-8`, `cp949`, `cp1250` 등) + 사용자가 직접 선택 가능, **구분자 자동 감지**(폴란드/유럽 환경은 세미콜론 `;`이 흔함) + 직접 선택 가능.
- 모든 값은 **문자열**로 다룬다.
  - 숫자: `1200.0` 같이 불필요한 `.0`은 제거해 `1200`으로. 소수는 원문 그대로.
  - 날짜: 기본 `YYYY-MM-DD`. 데이터 패널에서 형식 변경 가능(MVP는 매크로 단위 하나의 형식).
  - 팁: 정확한 형태가 필요한 열은 Excel에서 **텍스트 형식**으로 두도록 안내한다.
- 완전히 빈 행은 건너뛴다.
- 행 번호는 **원본 파일의 행 번호**로 표시한다 (헤더 제외한 데이터 행 번호도 함께 표기 가능).
- 데이터 파일이 매크로가 저장된 PC에 없을 수 있으므로, 열 때 파일 위치를 다시 묻는다. 열 이름이 `{변수}`와 맞는지 매핑 검사를 수행한다.

### 10.2 변수 문법

- `{열이름}` — 대소문자 구분. 열 이름에 공백이 있어도 허용 (`{Vendor Name}`).
- 리터럴 중괄호가 필요하면 `{{` 와 `}}`.
- 입력 칸에서 `{`를 치거나 **[Insert column ▾]** 버튼을 누르면 열 이름 목록이 나타난다.
- 존재하지 않는 열을 참조하면 편집 화면에서 빨간색 표시, 실행 전 검사에서 **차단**.

### 10.3 Status 열과 데이터 패널

데이터 패널(표)에 `Status` 열을 붙여 보여준다.

```
 Row  Vendor      Amount   Status
  1   ACME        1,200    ✅ Done
  2   Globex      850      ✅ Done
  3   Initech     2,400    ❌ Failed (step 5: save.png not found)
  4   Umbrella    310      ⏳ Pending
```

| Status | 의미 |
|---|---|
| Pending | 아직 실행 안 됨 |
| Done | 성공 |
| Failed | 실패로 중지됨 |
| Interrupted | 사용자가 중지(F12/Stop)함 → 입력이 어디까지 됐는지 불확실 |
| Skipped | 사용자가 건너뛰기로 표시 |

### 10.4 결과 CSV

- **원본 데이터 파일은 절대 수정하지 않는다.**
- 결과는 `Results` 폴더에 `<macro name>__<data file stem>__results.csv` 로 저장한다.
- **행 하나가 끝날 때마다 즉시 기록하고 flush**한다 (앱이 비정상 종료해도 기록이 남게).
- 행 시작 시 `Running` 상태를 먼저 기록한다. 이후 앱이 죽어서 `Running`이 남아 있으면 다음 실행 때 `Interrupted`로 간주한다.

컬럼

| 컬럼 | 설명 |
|---|---|
| `run_id` | 실행 ID (UUID 또는 타임스탬프) |
| `row_number` | 원본 파일 행 번호 |
| `row_hash` | 해당 행 값들의 해시 (데이터가 바뀌었는지 감지) |
| `status` | Running / Done / Failed / Interrupted / Skipped |
| `failed_step_id` | 실패한 동작 ID |
| `failed_step_label` | 사람이 읽는 동작 설명 |
| `reason` | 실패 사유 |
| `screenshot` | 실패 스크린샷 파일명 |
| `started_at`, `finished_at` | ISO 8601 |
| `duration_sec` | 소요 시간 |
| `macro_name`, `macro_version_hash` | 어떤 매크로로 실행했는지 |
| `speed` | Normal / Slow / Very slow |

한 행이 여러 번 실행될 수 있으므로(재시도 등) **행 단위 현재 상태 = 해당 행의 마지막 기록**으로 계산한다.

### 10.5 이어서 실행

1. 같은 데이터 파일 + 같은 매크로를 열면 결과 CSV를 읽어 Status 열을 복원한다.
2. 데이터 파일의 `row_hash`가 결과 CSV와 다르면 경고한다: "The data changed since the last run."
3. Run 버튼을 누르면 **첫 번째 Pending 행**부터 시작하도록 제안한다 (`Start from row` 칸에서 변경 가능).
4. **Failed / Interrupted 행은 자동으로 다시 실행하지 않는다.** 이미 일부가 입력되었을 수 있으므로 사용자가 행별로 선택한다.
   - **Retry this row**: 처음부터 다시 실행
   - **Skip this row**: Skipped로 표시
   - **Mark as Done**: 사용자가 화면에서 직접 확인하고 완료 처리
5. 특정 행 범위만 실행 (예: 10~50행) 가능.

---

## 11. 안전장치와 실행 전 검사

### 11.1 안전장치

| 장치 | 설명 |
|---|---|
| **비상 정지 F12** | `RegisterHotKey` 기반 전역 단축키. 설정에서 변경 가능. 실행 시작 시 등록 성공 여부 확인, 실패하면 실행을 막고 다른 키를 선택하게 한다 |
| 카운트다운 | 실행 시작 전 5초(설정 가능). 대상 화면으로 전환할 시간 |
| 해상도 경고 | 앱 시작 시 해상도/배율을 읽어 상태바에 표시. 매크로 `recorded_screen`과 다르면 ⚠ 표시 + 실행 전 확인 |
| 화면 절전 방지 | 실행 중 `SetThreadExecutionState(ES_CONTINUOUS \| ES_SYSTEM_REQUIRED \| ES_DISPLAY_REQUIRED)` |
| 화면 사용 불가 감지 | 캡처 실패/블랙 화면 → 즉시 중지 |
| 중복 실행 방지 | 앱 인스턴스당 한 번에 하나의 매크로만 실행 |
| 플로팅 패널 충돌 방지 | 클릭 대상 좌표가 패널 영역 안이면 패널을 다른 구석으로 자동 이동 (아래 11.3) |

### 11.2 실행 전 검사 (Pre-flight)

Run 버튼을 누르면 아래 검사를 수행하고 결과를 **확인 화면**에 표시한다.
- 🔴 **오류**: 해결 전까지 시작 불가
- 🟡 **경고**: 확인 후 시작 가능

| 검사 | 수준 |
|---|---|
| 매크로 구조/스키마 유효성 | 🔴 |
| 참조된 이미지 파일 존재 | 🔴 |
| `{변수}`가 가리키는 열이 데이터에 존재 | 🔴 |
| 데이터 파일 읽기 성공, 대상 행 수 | 🔴 |
| 참조된 열 중 **빈 값**이 있는 행 (행 목록 표시, 해당 행을 Skip으로 표시하거나 수정 필요) | 🔴 |
| 비상 정지 단축키 등록 가능 | 🔴 |
| 현재 해상도/배율 ≠ 매크로 기록 해상도 | 🟡 (강한 경고 문구) |
| 모니터가 2개 이상 | 🟡 |
| **Verify가 하나도 없는 Per Row 매크로** ("저장 버튼 같은 핵심 동작에는 Verify를 권장합니다") | 🟡 |
| 데이터가 이전 실행 이후 변경됨 (row_hash 불일치) | 🟡 |
| 클릭 좌표가 플로팅 패널 기본 위치와 겹침 | 🟡 |
| 결과 CSV에 Failed/Interrupted 행이 있음 | 🟡 (처리 방법 선택 유도) |

실행 확인 화면 구성 (와이어프레임)
```
Ready to run "Invoice Entry"
 Data: invoices.xlsx — 148 rows       Start from row: [37 ▾]  (Resume from 37)
 Range: [All remaining ▾]   Speed: (•) Normal  ( ) Slow +0.5s  ( ) Very slow +1s
 ☐ Skip Setup   ☐ Skip Cleanup   ☐ Step-by-step
 Screen check: ✅ 1920×1080 @125%
 Checks: 🟡 No Verify images in Per Row (recommended for the Save step)
 Starts in 5… (switch to your target window now)      [Run 1 row] [Start] [Cancel]
```

### 11.3 플로팅 패널과 화면 캡처의 상호작용 (중요)

플로팅 패널은 대상 화면 위에 떠 있으므로 두 가지 문제가 생길 수 있다.

1. **패널이 클릭 대상 위를 가려서** 클릭이 패널에 전달됨 → 클릭 직전에 대상 좌표가 패널 영역과 겹치면 패널을 반대편 구석으로 이동한다.
2. **패널이 화면 캡처에 찍혀서** 이미지 매칭을 방해함 → 패널 창에 `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`를 적용해 캡처에서 제외하는 방법을 시도하고, **M0/M4에서 실제 클라우드 PC에서 동작하는지 검증**한다. 안 되면 패널을 이미지 검색 직전에 숨겼다가 다시 표시하는 방식을 사용한다.

추가 요구사항
- 패널은 **포커스를 빼앗지 않아야** 한다 (`Qt.WindowDoesNotAcceptFocus`, `WA_ShowWithoutActivating`, 필요 시 `WS_EX_NOACTIVATE`). 포커스를 빼앗으면 대상 프로그램의 입력창에 타이핑이 가지 않는다.
- 항상 위(Always on top), 프레임 없는 작은 창, 드래그 이동 가능.

---

## 12. UI/UX 명세

### 12.1 메인 화면 (와이어프레임)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Stepwise  [▶ Run] [⏸ Pause] [■ Stop]  [Step-by-step ☐]   Data: invoices.xlsx ▾ │
├────────────────┬─────────────────────────────────────────────────────────────┤
│ MACROS         │ Invoice Entry              Rows: 148   Recorded: 1920×1080@125 │
│ 🔍 search      │ 🔍 filter ▾   [Compact ☐]                                      │
│ ▸ Invoice Entry│ ┌───┬───┬───────────────┬─────────────────┬──────┬─────┬─────┐│
│   Credit Check │ │ # │ ✓ │ Action        │ Target          │ Wait │Check│Note ││
│   Daily Login  │ ├───┴───┴───────────────┴─────────────────┴──────┴─────┴─────┤│
│   [+ New]      │ │ ▼ SETUP (runs once)                                         ││
│                │ │ 1 ✓ Click        (320,180)             0.2s        Open menu││
│                │ │ 2 ✓ Wait Image   menu_open.png         max 10s             ││
│                │ │ ▼ PER ROW (runs for each data row)                          ││
│                │ │ ▸ Fill vendor info (3 steps)                                ││
│                │ │ 6 ✓ Click Image  save.png              0.2s     🖼 Verify    ││
│                │ │ ▼ CLEANUP (runs once at the end)                            ││
│                │ │ 7 ✓ Key          Esc                   0.2s                 ││
│                │ └─────────────────────────────────────────────────────────────┘│
│                │ [+ Add action ▾] [↑][↓] [Duplicate] [Delete] [Group]            │
├────────────────┴─────────────────────────────────────────────────────────────┤
│ Properties (selected action)                    │ Preview / Data                 │
│ Type: Click  X: 500  Y: 220  [📍 Pick F8]        │ [captured image / position]    │
│ Wait before: 0.2s   Guard: [📷 Capture F9] …     │ [Show on screen] [Test match]  │
├──────────────────────────────────────────────────────────────────────────────┤
│ Screen 1920×1080 @125%  ✅ matches macro        Lock: editing   Log: Ready      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 동작 목록(Action Tree)

- **한 목록에 3구역 헤더 행**(SETUP / PER ROW / CLEANUP)을 표시한다. 탭으로 나누지 않는다 (전체 흐름이 한눈에 보이도록).
- 구성: 트리 뷰(구역 → 그룹 → 동작). 구역 헤더는 이동/삭제 불가, 접기/펼치기 가능.
- 열: `#`(실행 순번, 헤더/그룹 제외), `✓`(Enabled 체크), `Action`, `Target`(사람이 읽는 요약), `Wait`, `Check`(Guard/Verify 아이콘), `Note`.
- **Target 요약은 문장형**: `Click vendor field (500,220)`처럼, Note가 있으면 Note를 우선 표시한다.
- 드래그 앤 드롭으로 순서 변경, 구역 간 이동 가능. 그룹 안으로/밖으로 이동 가능. (그룹 중첩 불가, 구역 헤더 이동 불가)
- 다중 선택 + 복사/붙여넣기/삭제/활성 토글.
- **실행 중인 줄 하이라이트 + 자동 스크롤**(항상 화면 중앙 근처). 실패한 줄은 빨간색 강조.
- 행 높이: **Normal / Compact** 두 가지.
- 목록 위 검색칸 + 필터: `Guard/Verify 있는 동작만`, `비활성 동작만`, `변수 사용하는 동작만`.
- 그룹: `▸ Fill vendor info (3 steps)`처럼 접으면 한 줄. 그룹 만들기는 선택한 동작들에서 [Group] 버튼.

### 12.3 속성 패널 (Properties)

- 선택한 동작 타입에 맞는 입력 폼을 동적으로 표시한다.
- **Pick (F8)**: 좌표를 화면에서 직접 찍는 모드(Stepwise 창을 최소화하고 전체 화면 오버레이 표시, 클릭한 위치 사용).
- **Capture (F9)**: 화면 영역을 드래그해서 이미지로 저장.
- 입력 필드에서 `{` 입력 시 열 이름 자동완성.
- 이미지 조건 폼: 이미지 미리보기, Region(Full screen / Around capture / Custom), Confidence(프리셋/슬라이더, 고급 접힘), Timeout, After found, Stable for(고급).
- 버튼: **[Test this step]**, **[Show on screen]**(좌표에 빨간 십자를 1~2초 표시), **[Test match]**.
- 값 검증 즉시 표시(빈 필드, 범위 오류 등).

### 12.4 캡처 도우미 (Capture Helper)

- **편집 모드에서만** 전역 단축키 F8/F9가 활성화된다 (실행 중에는 비활성).
- **F8**: 현재 마우스 좌표를 읽어 **Click 동작을 선택한 위치 다음에 추가**한다.
- **F9**: 화면을 즉시 캡처해 고정 이미지로 띄우고(오버레이 뒤 배경이 변하지 않도록) 드래그로 영역 선택 → 이미지 저장 → 현재 선택된 동작의 이미지로 연결(또는 새 Click image/Wait for image 추가).
- 속성 패널의 `[Pick]`/`[Capture]` 버튼도 같은 기능을 제공한다.
- 단축키 충돌을 대비해 설정에서 F8/F9도 변경 가능하게 한다.

### 12.5 데이터 패널

- Data 드롭다운에서 파일 선택/변경. 시트, 헤더 행, 인코딩, 구분자 설정.
- 미리보기 표(행 번호, 열들, **Status**). 행 우클릭: `Retry this row / Skip this row / Mark as Done / Run only this row`.
- 열 헤더 클릭 시 해당 `{열이름}`을 현재 입력 칸에 삽입.

### 12.6 실행 중 화면: 플로팅 패널

```
┌──────────────────────────────┐
│ Stepwise ▶ Running           │
│ Row 37 / 148  ████░░░░░ 25%  │
│ Step 4: Type {Vendor}        │
│ OK 36   Failed 0             │
│ Speed: Normal                │
│ [⏸ Pause]  [■ Stop]          │
│ Emergency stop: F12          │
└──────────────────────────────┘
```

- 실행 시작 시 메인 창은 최소화되고 패널만 표시한다.
- 실패 시: 패널에 사유를 표시하고 메인 창을 복원하여 해당 줄을 강조한다.
- Step-by-step 모드에서는 `Next` 버튼 추가.

### 12.7 실행 종료 요약

- 성공/실패/건너뜀 건수, 소요 시간, 평균 행당 시간.
- 실패가 있으면: 실패 행/단계/사유, 스크린샷 열기, **Open results CSV**, 이어서 실행 안내.

### 12.8 설정 화면

| 구분 | 항목 |
|---|---|
| General | Library folder, Results folder, 카운트다운 초(기본 5), 로그 보관 |
| Hotkeys | Emergency stop (F12), Pause/Resume (F11, 제안), Capture position (F8), Capture image (F9) |
| Timing | Default wait before (0.2s), Poll interval (0.25s) |
| Image (Advanced) | Default confidence preset (Strict), Grayscale matching, Stable-for 기본값 |
| Typing | Default type mode (Paste / Keystrokes), Clipboard restore |
| About | 버전, 로그 폴더 열기 |

### 12.9 인앱 단축키 (제안)

| 키 | 동작 |
|---|---|
| Ctrl+S | 저장 |
| Ctrl+Z / Ctrl+Y | Undo / Redo |
| Ctrl+C / V / D | 복사 / 붙여넣기 / 복제 |
| Delete | 삭제 |
| Space | 선택 동작 Enabled 토글 |
| F5 | Run |
| F6 | Test this step |

### 12.10 Undo/Redo, 자동 저장

- `QUndoStack`(커맨드 패턴)으로 모든 편집(추가/삭제/이동/속성 변경/그룹 생성)을 되돌릴 수 있게 한다.
- 30초 또는 변경 N회마다 `recovery\`에 자동 저장하고, 비정상 종료 후 시작 시 복구를 제안한다.

### 12.11 UX 원칙

- 위험한 동작(삭제, 덮어쓰기)은 확인 대화상자 또는 Undo로 보호.
- 상태바의 해상도 표시는 항상 보인다: 일치 ✅ / 불일치 ⚠(빨강).
- 에러는 평문 영어로, 해결 방법을 함께 안내.
- 모든 아이콘 버튼에는 툴팁.

---

## 13. 공유와 라이브러리

### 13.1 라이브러리

- 설정의 Library folder 안의 `.swm` 파일 목록을 왼쪽 패널에 표시한다 (이름, 수정 시각, 기록 해상도, 잠금 상태).
- 폴더를 **공유 드라이브/OneDrive**로 지정하면 팀 공용 라이브러리가 된다.
- 검색, 새 매크로, 복제, 이름 바꾸기, 삭제(휴지통 이동 또는 확인 후 삭제), 파일에서 가져오기(Import), 내보내기(Export).
- 폴더 변경 감지: 앱이 열려 있는 동안 주기적(또는 파일 시스템 감시)으로 목록을 갱신.

### 13.2 편집 잠금

공유 폴더에서 두 사람이 동시에 같은 매크로를 수정해 덮어쓰는 사고를 막는다.

- 편집 시작 시 `<name>.swm.lock` 파일을 생성한다: `{user, machine, started_at, heartbeat_at}`.
- 편집 중 주기적으로(예: 30초) `heartbeat_at`을 갱신한다.
- 다른 사용자가 열면 **읽기 전용**으로 열고 "Being edited by <user>"를 표시한다. (읽기 전용에서도 **실행은 가능**)
- 잠금이 오래된 경우(예: heartbeat가 5분 이상 갱신 안 됨)는 "Stale lock — take over?"로 인수 가능.
- 저장 직전에 파일의 수정 시각이 열었을 때와 다르면 덮어쓰기 경고.
- "Save as copy" 제공.

### 13.3 해상도 불일치 경고

- 매크로를 열 때와 실행 전에 `recorded_screen`과 현재 화면을 비교한다.
- 불일치 시: "This macro was recorded at 1920×1080 @125%. Your screen is 1600×900 @100%. Clicks and images may not match." + [Run anyway] [Cancel].
- 저장할 때 `recorded_screen`을 **현재 화면 정보로 갱신**할지 묻는다 (좌표를 새로 찍은 경우에만 의미 있음).

### 13.4 보안/개인정보 주의

- 매크로에 **비밀번호를 넣지 않도록** 안내 문구를 표시한다 (Type text 입력창 근처 도움말).
- 실패 스크린샷과 결과 CSV에는 업무 데이터가 포함될 수 있으므로 **로컬 Results 폴더**에 저장하며 `.swm`에 포함하지 않는다.
- 로그에는 입력한 데이터 값(변수 치환 결과)을 기록하지 않는다 (동작 종류와 행 번호만). 디버그 모드에서만 선택적으로 기록.

---

## 14. 패키징과 배포

### 14.1 빌드

- **PyInstaller onedir**로 빌드한다 (onefile은 시작이 느리고 백신 오탐이 더 잦음).
- 사용하지 않는 Qt 모듈, 불필요한 라이브러리를 제외해 크기를 줄인다 (목표: 설치 파일 100~150MB 이하).
- 앱 아이콘, 버전 정보(메타데이터) 포함.

### 14.2 설치 파일 (Inno Setup)

- `PrivilegesRequired=lowest`, 설치 경로 `{localappdata}\Programs\Stepwise` (관리자 권한 불필요).
- 시작 메뉴 바로가기, 선택적 바탕화면 바로가기.
- `.swm` 파일 연결(사용자 단위 레지스트리, HKCU) — 더블클릭하면 Stepwise에서 열기.
- 제거(Uninstall) 지원. 사용자 설정/매크로/결과는 기본적으로 삭제하지 않는다.
- 버전 업그레이드: 같은 AppId로 덮어쓰기 설치.

### 14.3 백신/IT 정책

- 서명되지 않은 exe는 백신이 오탐할 수 있으므로 **사내 IT에 사전 허용(화이트리스트) 요청**을 준비한다(설치 파일 해시, 설치 경로 제공).
- 코드 서명 인증서 검토는 미결정 항목(섹션 18).
- 배포는 팀 공유 폴더에 `Stepwise-Setup-x.y.z.exe`를 올리는 방식.

---

## 15. 개발 마일스톤과 단계별 프롬프트

> 각 마일스톤은 이전 마일스톤이 완료 기준을 통과한 뒤에만 시작한다.
> 아래 프롬프트는 이 문서를 컨텍스트로 첨부한 상태에서 AI 개발 도우미에게 그대로 붙여 넣어 사용하는 용도다.

### M0. 환경 검증 스파이크 (가장 먼저)

**목적**: 실제 **Azure 클라우드 PC**에서 핵심 기술이 되는지 확인한다. 이것이 안 되면 이후 설계를 조정해야 한다.

**산출물**: `tools/spike/` 아래의 독립 실행 스크립트와 결과 리포트(`docs/m0-report.md`)

**검증 항목**
1. Python 설치(또는 PyInstaller exe)가 클라우드 PC에서 실행되는가
2. DPI/해상도/배율 조회가 정확한가 (100%, 125%, 150%에서)
3. 좌표 클릭이 정확한가 (`SendInput`, DPI aware 상태에서 목표 위치에 정확히 클릭)
4. 화면 캡처와 템플릿 매칭이 되는가 (속도, 일치율)
5. **클립보드 붙여넣기**가 되는가 / 안 되면 **유니코드 키 입력**이 되는가 (한글, 폴란드어 문자 포함)
6. **F12 전역 단축키**가 원격 접속 클라이언트에서 정상적으로 전달되는가
7. 접속 창을 최소화/세션 잠금했을 때 캡처·입력이 어떻게 되는가
8. `WDA_EXCLUDEFROMCAPTURE`가 캡처에서 창을 제외하는가
9. 대상 시스템(SAP/ERP/웹/사내 프로그램)이 **관리자 권한으로 실행**되는가 (그렇다면 일반 권한 입력이 막힘)

**완료 기준**: 위 항목별 O/X와 측정 수치가 `m0-report.md`에 기록되고, 실패 항목은 대안(예: keystrokes 모드 기본값, 단축키 변경)이 제시된다.

**프롬프트**
```
첨부한 Stepwise 개발 가이드의 M0를 진행해줘.
tools/spike/ 아래에 독립 실행 스크립트로 섹션 15 M0의 9가지 검증 항목을 각각 확인할 수 있는 코드를 만들어줘.
각 스크립트는 사람이 읽을 수 있는 결과(OK/FAIL, 측정값)를 콘솔에 출력하고, 마지막에 docs/m0-report.md에 붙여 넣을 수 있는 마크다운 표를 출력해줘.
Python 3.12, ctypes SendInput, mss, opencv-python-headless만 사용하고 UI 코드는 만들지 마.
스크립트 실행 방법과 클라우드 PC에서 테스트하는 순서를 README로 정리해줘.
```

---

### M1. 핵심 엔진 (UI 없음)

**산출물**: `services/`(input_win, clipboard, screen, matcher, hotkeys, power), `engine/`의 기본 실행 루프, CLI 테스트 러너, 단위 테스트

**범위**
- `input_win.py`: 마우스 이동/클릭(버튼, 더블클릭), 키 조합, 유니코드 키 입력
- `clipboard.py`: 저장 → 설정 → Ctrl+V → 복원
- `screen.py`: 캡처, 해상도/배율 조회, 블랙 화면 감지
- `matcher.py`: 섹션 8 명세대로 매칭, 최고 일치율/위치 반환, 폴링과 timeout
- `hotkeys.py`: RegisterHotKey 기반 F12
- `engine/timing.py`: wait_before + speed_extra, 중단 가능한 sleep
- `engine/actions.py`: 섹션 7의 모든 동작 구현(Guard/Verify 포함)
- `engine/runner.py`: 3구역 실행, 행 반복(데이터는 우선 메모리 상의 리스트로), 실패 시 중지, 스크린샷 저장
- `core/variables.py`: 변수 파싱/치환/이스케이프
- `tools/dummy_erp.py`: 텍스트 입력칸, 버튼, "Saved" 문구가 뜨는 간단한 테스트 앱

**완료 기준**
- 변수 치환, timing(Speed 포함), 실패 처리에 대한 단위 테스트 통과
- CLI로 JSON 매크로 하나를 실행해 `dummy_erp.py` 폼에 3~5행을 정확히 입력
- F12로 어느 시점에서든(대기 중 포함) 즉시 중단
- 이미지가 안 나올 때 timeout 후 중지하고 스크린샷이 저장됨

**프롬프트**
```
첨부한 Stepwise 개발 가이드의 M1을 진행해줘. 섹션 5(아키텍처), 7(동작), 8(이미지), 9(엔진)를 정확히 따라줘.
UI는 만들지 말고, 엔진과 서비스, 그리고 CLI 러너(python -m stepwise.cli run macro.json --data data.csv)만 구현해줘.
모든 대기는 중단 가능해야 하고(threading.Event), time.sleep을 직접 쓰지 마.
Speed(Normal/Slow/Very slow)는 섹션 9.3의 규칙대로 wait_before에만 더해줘.
tools/dummy_erp.py 테스트 앱과 pytest 단위 테스트를 함께 만들고, 구현이 끝나면 완료 기준 항목별로 결과를 보고해줘.
```

---

### M2. 파일 형식과 데이터 연동

**산출물**: `core/models.py`, `schema.py`, `package.py`, `migration.py`, `services/data_source.py`, `engine/results.py`, `engine/preflight.py`

**범위**
- 섹션 6의 모델/스키마, `.swm` 읽기/쓰기(atomic write), 이미지 포함
- xlsx/csv 읽기(인코딩·구분자 감지, 값 정규화 규칙: 섹션 10.1)
- 결과 CSV 기록/복원(섹션 10.4), 행 상태 계산, row_hash
- 이어서 실행 로직(섹션 10.5)
- Pre-flight 검사(섹션 11.2) — 결과를 구조화된 목록(수준, 메시지)으로 반환
- `.swm` 편집 잠금(`services/lock.py`)

**완료 기준**
- 저장 → 열기 왕복(round-trip) 후 내용 동일
- 한글/폴란드어가 포함된 xlsx, `;` 구분 cp1250 CSV, `utf-8-sig` CSV를 모두 올바르게 읽음
- 중간에 강제 종료한 시나리오에서 다음 실행 때 첫 Pending 행을 정확히 제안하고, Failed/Interrupted 행은 자동 재실행하지 않음
- 데이터가 변경된 경우 row_hash 불일치를 감지
- 잠금 파일 생성/갱신/stale 처리 테스트 통과

**프롬프트**
```
첨부한 Stepwise 개발 가이드의 M2를 진행해줘. 섹션 6, 10, 11.2, 13.2를 정확히 따라줘.
M1의 엔진이 새 모델(core/models.py)을 사용하도록 연결하고, CLI에서 .swm 파일과 데이터 파일을 받아 실행/이어서 실행이 되게 해줘.
결과 CSV는 행이 끝날 때마다 flush해야 하고, Running 상태가 남은 행은 다음 실행 때 Interrupted로 취급해줘.
Pre-flight는 UI와 무관하게 (level, message, details) 목록을 반환하는 함수로 만들어줘.
pytest로 round-trip, 인코딩, 이어서 실행, row_hash, 잠금 테스트를 작성해줘.
```

---

### M3. 메인 UI: 동작 목록과 속성 패널

**산출물**: `ui/main_window.py`, `macro_library.py`, `action_tree.py`, `properties_panel.py`, `data_panel.py`, `strings.py`, `styles.qss`

**범위**
- 섹션 12.1~12.5의 레이아웃: 라이브러리, 동작 트리(3구역 헤더 + 그룹 + 동작), 속성 패널, 데이터 패널
- 동작 추가/삭제/복제/이동(드래그 앤 드롭 규칙 포함), Enabled 토글, Note
- 구역/그룹 접기, 검색/필터, Compact 보기
- Undo/Redo, 자동 저장/복구
- 저장/열기, 라이브러리 목록, 잠금 상태 표시
- 상태바 해상도 표시와 불일치 경고
- 데이터 패널: 파일 선택, 미리보기, Status 열(결과 CSV 연동)
- 변수 `{` 자동완성, 존재하지 않는 열 빨간 표시
- (실행 연결은 M4에서 한다. 여기서는 Run 버튼이 Pre-flight 화면까지만 연결되어도 됨)

**완료 기준**
- 50개 이상의 동작을 가진 매크로를 열어도 스크롤/접기/검색이 매끄럽게 동작
- 모든 편집이 Undo/Redo 가능
- 앱을 강제 종료한 후 재시작하면 복구 제안이 표시됨
- UI 문자열이 전부 `strings.py`에 있고 영어
- 해상도가 다른 `.swm`을 열면 경고가 표시됨

**프롬프트**
```
첨부한 Stepwise 개발 가이드의 M3를 진행해줘. 섹션 12(UI/UX)와 13(공유/라이브러리)을 따라줘.
먼저 구현 계획(클래스 구조, 트리 모델 설계, 드래그 앤 드롭 제약 처리 방식)을 짧게 정리해서 보여주고, 승인하면 구현해줘.
동작 목록은 QTreeView + 커스텀 QAbstractItemModel로 구현하고, 편집은 모두 QUndoCommand로 만들어줘.
UI는 엔진 코드를 직접 만지지 말고 core 모델만 편집해야 해.
구현 후 스크린샷이나 실행 방법을 알려주고, 완료 기준 항목별로 결과를 보고해줘.
```

---

### M4. 실행 UI: 플로팅 패널, 실행 확인, 요약

**산출물**: `ui/preflight_dialog.py`, `run_panel.py`, `run_summary.py`, 엔진-UI 연결

**범위**
- 실행 확인 화면(섹션 11.2): 검사 결과, Start from row, 범위, **Speed 선택(Normal/Slow/Very slow)**, Skip Setup/Cleanup, Step-by-step, 카운트다운, Run 1 row
- 엔진을 별도 스레드에서 실행하고 시그널로 UI 갱신
- 플로팅 패널(섹션 12.6, 11.3): 포커스를 가져가지 않음, 항상 위, 이동 가능, 대상 좌표와 겹치면 자동 이동, 캡처 제외 시도
- 실행 중 메인 창 최소화, 현재 줄 하이라이트 + 자동 스크롤
- Pause/Resume/Stop, Step-by-step의 Next
- 실패 시 메인 창 복원, 실패 줄 강조, 실패 사유 표시
- 실행 종료 요약 화면, 결과 CSV 열기
- 데이터 패널 Status가 실행 중 실시간 갱신, 행 우클릭 메뉴(Retry/Skip/Mark as Done/Run only this row)

**완료 기준**
- `dummy_erp.py`를 대상으로 100행 데이터를 끝까지 자동 입력
- 중간에 F12로 중지 → 재시작 → 이어서 실행이 정확한 행에서 재개
- Speed Slow/Very slow에서 동작 사이 지연이 실제로 증가함을 로그로 확인
- 패널 때문에 클릭이 가로채이거나 이미지 매칭이 방해받지 않음
- 실패 시 스크린샷, 결과 CSV, 줄 강조가 모두 정상

**프롬프트**
```
첨부한 Stepwise 개발 가이드의 M4를 진행해줘. 섹션 9, 10, 11, 12.6~12.7을 따라줘.
Speed 선택(Normal/Slow +0.5s/Very slow +1s)을 실행 확인 화면에 넣고, 섹션 9.3 규칙대로 엔진에 전달해줘.
플로팅 패널은 포커스를 훔치지 않아야 하고, 클릭 대상 좌표와 겹치면 반대편 구석으로 이동해야 해. 캡처 제외(WDA_EXCLUDEFROMCAPTURE)를 시도하고 안 되면 이미지 검색 직전에 숨기는 방식으로 폴백해줘.
엔진 스레드와 UI 스레드의 통신은 시그널로만 해줘.
tools/dummy_erp.py로 100행 E2E 테스트 절차를 문서화하고 결과를 보고해줘.
```

---

### M5. 편의 기능과 안전장치 마무리

**산출물**: `ui/capture_overlay.py`, `settings_dialog.py`, 나머지 편의 기능

**범위**
- 캡처 도우미: F8 좌표 추가, F9 영역 이미지 캡처, Pick 버튼, Region 지정 오버레이
- Show on screen(좌표 십자 표시), Test this step, Test match(일치율 표시)
- 설정 화면(섹션 12.8): 단축키 변경(충돌/등록 실패 처리), 기본 지연, 정확도 프리셋, 입력 방식, 폴더
- 인앱 단축키(섹션 12.9)
- 에러 메시지 문구 정리, 툴팁, 비밀번호 입력 금지 안내문
- 로그 보관/열기
- 화면 절전 방지 적용 확인

**완료 기준**
- F9로 만든 이미지를 Click image에 연결하고 Test match가 일치율을 표시
- F12/F8/F9를 다른 키로 변경해도 정상 동작, 이미 사용 중인 키는 경고
- Test this step으로 개별 동작이 정확히 1회만 실행됨

**프롬프트**
```
첨부한 Stepwise 개발 가이드의 M5를 진행해줘. 섹션 8.4~8.5, 12.3~12.4, 12.8~12.9를 따라줘.
캡처 오버레이는 먼저 화면을 캡처해서 정지된 이미지를 보여준 뒤 그 위에서 영역을 선택하게 해줘(배경이 변하지 않도록).
F8/F9 전역 단축키는 실행 중에는 해제하고 편집 모드에서만 등록해줘.
Test match는 임계값 미달이어도 최고 일치율과 위치를 보여줘야 해.
```

---

### M6. 패키징과 설치 파일

**산출물**: `installer/stepwise.spec`, `installer/setup.iss` (기존 `stepwise.iss`는 호환 wrapper), 빌드 스크립트, 설치/제거 테스트 결과

**범위**: 섹션 14 전체

**완료 기준**
- 깨끗한 Windows(Python 미설치)에서 `Setup.exe`만으로 설치/실행/제거 가능
- 관리자 권한 없이 사용자 폴더에 설치됨
- `.swm` 더블클릭 시 Stepwise에서 열림
- 설치 파일 크기와 첫 실행 시간 기록

**프롬프트**
```
첨부한 Stepwise 개발 가이드의 M6를 진행해줘. 섹션 14를 따라줘.
PyInstaller onedir 빌드 스펙, Inno Setup 스크립트(PrivilegesRequired=lowest, {localappdata}\Programs\Stepwise, .swm 파일 연결)를 만들고, 한 번에 빌드되는 scripts/build.ps1을 작성해줘.
불필요한 Qt 모듈을 제외해 크기를 줄이고, 결과 크기를 보고해줘.
IT 부서에 전달할 화이트리스트 요청용 정보(설치 경로, 파일 해시, 동작 설명)를 docs/it-request.md로 작성해줘.
```

---

### M7. QA와 파일럿

**범위**
- 실제 클라우드 PC에서 해상도/배율 매트릭스 테스트 (100/125/150%)
- 실제 업무 시스템(SAP/ERP/웹)에서 소규모 파일럿 (팀원 2~3명, 10~30행)
- 피드백 수집 → 우선순위 조정 → 패치 릴리스
- 사용자 안내서(영어, 1~2페이지) 작성: 설치, 첫 매크로 만들기, 이어서 실행, 문제 해결

**완료 기준**: 파일럿 팀원이 안내서만 보고 스스로 매크로를 만들고 데이터 매크로를 실행할 수 있다.

---

## 16. 테스트 전략

### 16.1 자동 테스트 (pytest)

| 대상 | 내용 |
|---|---|
| 변수 치환 | 기본, 이스케이프(`{{ }}`), 없는 열, 공백 열 이름, 빈 값 |
| 스키마 | 정상/비정상 JSON, 버전 마이그레이션, 신버전 파일 거부 |
| 패키지 | zip round-trip, 이미지 포함, atomic write |
| 데이터 | xlsx(한글/폴란드어), csv(utf-8-sig, cp949, cp1250, `;`/`,`), 숫자 `.0` 제거, 날짜 형식, 빈 행 |
| 결과/이어서 | 첫 Pending 제안, Failed/Interrupted 처리, row_hash 불일치, `Running` 잔존 처리 |
| 타이밍 | wait_before 우선순위(동작 > 매크로), Speed 적용 범위(적용/비적용 항목), 중단 가능한 sleep |
| 매처 | 합성 이미지로 일치/불일치/임계값 경계, region 처리 |
| Pre-flight | 각 검사 항목의 수준과 메시지 |
| 잠금 | 생성/갱신/stale 인수 |

### 16.2 E2E 테스트 (dummy_erp.py)

- 폼에 텍스트 입력칸 3개, 저장 버튼, "Saved" 표시, 느린 응답(랜덤 지연), 가끔 팝업을 띄우는 옵션을 가진 가짜 앱.
- 시나리오: 정상 100행, 중간 F12 중지 후 이어서, 이미지 timeout 실패, Speed Slow, 한글/폴란드어 입력, Verify 실패 감지.

### 16.3 수동 테스트 체크리스트 (클라우드 PC)

- [ ] 해상도 100% / 125% / 150%에서 좌표 클릭 정확도
- [ ] 이미지 매칭 일치율과 속도
- [ ] 클립보드 붙여넣기 / 키 입력 방식 (한글, 폴란드어)
- [ ] F12가 접속 클라이언트에서 전달됨
- [ ] 플로팅 패널이 포커스를 훔치지 않음, 클릭/매칭 방해 없음
- [ ] 세션 최소화/잠금 시 동작(실패 처리)
- [ ] 관리자 권한 프로그램 대상 입력
- [ ] 공유 폴더에서 두 명이 동시에 열기(잠금)
- [ ] 설치/제거/업그레이드

---

## 17. 알려진 함정 체크리스트

| 함정 | 대응 |
|---|---|
| **DPI 배율**(125%, 150%)로 좌표가 어긋남 | 물리 픽셀 기준으로 통일, M0에서 배율별 검증, 상태바 표시 |
| **멀티 모니터** 좌표 | MVP는 기본 모니터만, 2개 이상이면 경고 |
| **관리자 권한으로 실행 중인 프로그램**에 입력이 안 들어감 | M0에서 확인, 필요 시 Stepwise도 관리자 권한 실행 안내 (설치는 사용자 권한 유지) |
| **한글 입력 깨짐**(IME) | 기본 클립보드 붙여넣기, 대안으로 유니코드 키 입력 |
| **원격 환경의 클립보드 리디렉션 차단** | keystrokes 모드 제공, M0에서 검증 |
| **원격 세션 끊김/잠금** 시 입력 불가 | 블랙 화면 감지로 중지, 절전 방지, 사용자 안내 |
| 원격 클라이언트가 **F12 등 키를 가로챔** | 단축키 변경 가능, M0에서 검증 |
| 플로팅 패널이 **클릭을 가로채거나 매칭을 방해** | 자동 이동, 캡처 제외/숨김 폴백, 포커스 비활성 |
| 이미지 **일시적 깜빡임**(로딩 팝업 등) | `stable_for` 옵션 |
| 이중 입력 사고 | 실패 행 자동 재실행 금지, Status와 사용자 선택 |
| 공유 폴더 **동시 편집 덮어쓰기** | 잠금 파일, 저장 전 수정 시각 확인 |
| 데이터 파일이 실행 사이에 **변경됨** | row_hash 비교 경고 |
| Excel 숫자/날짜 형식 문제 | 값 정규화 규칙, 텍스트 형식 권장 |
| CSV **구분자/인코딩** 문제 | 자동 감지 + 수동 선택 |
| 백신 오탐 | onedir, IT 화이트리스트, 코드 서명 검토 |
| 팀원 간 **해상도 다름** | `recorded_screen` 기록과 경고, 이미지 영역 지정으로 완화 |
| 매크로에 **비밀번호 저장** | 금지, 안내 문구 |

---

## 18. 미결정 항목 (결정 필요)

| # | 항목 | 현재 제안 | 결정 시점 |
|---|---|---|---|
| 1 | 실패 시 **Cleanup 자동 실행 여부** | 실행하지 않음 (화면 상태를 알 수 없으므로) | M4 전 |
| 2 | 원격 접속 방식(RDP / AVD / 웹 클라이언트)과 키/클립보드 동작 | M0에서 검증 후 확정 | M0 |
| 3 | 멀티 모니터 정책 | MVP는 기본 모니터만 + 경고 | M3 전 |
| 4 | 기본 Confidence 값 | Strict = 0.95 (M0 측정으로 조정) | M0 |
| 5 | 코드 서명 인증서 | IT 화이트리스트 먼저, 필요 시 검토 | M6 |
| 6 | 결과 폴더 기본 위치와 스크린샷 보관 기간 | `Documents\Stepwise\Results`, 보관 기간은 설정으로 | M2 |
| 7 | Pause/Resume 전역 단축키(F11) 채택 여부 | 제안 상태 | M5 |
| 8 | 편집 잠금 stale 기준 시간 | 5분 | M2 |
| 9 | 앱 아이콘/브랜딩 | 임시 아이콘 | M6 |
| 10 | 매크로 변수 확장(`{Today}` 등) 시기 | MVP 이후 | MVP 후 |

---

## 부록 A. 매크로 파일 예시 (macro.json)

```json
{
  "schema_version": 1,
  "id": "6f0c1d52-8c1b-4b0e-9a55-2f6e7d1b9c10",
  "name": "Invoice Entry",
  "description": "Enter vendor invoices into the ERP form.",
  "created_by": "user01",
  "created_at": "2026-10-03T09:00:00+02:00",
  "modified_at": "2026-10-03T09:30:00+02:00",
  "recorded_screen": { "width": 1920, "height": 1080, "scale_percent": 125, "monitor_count": 1 },
  "settings": {
    "default_wait_before": 0.2,
    "image_confidence": 0.95,
    "poll_interval": 0.25,
    "type_mode": "paste"
  },
  "data_source": {
    "type": "xlsx",
    "file_hint": "invoices.xlsx",
    "sheet": "Sheet1",
    "header_row": 1,
    "encoding": null,
    "delimiter": null
  },
  "setup": [
    {
      "id": "a1", "type": "click", "enabled": true, "note": "Open menu",
      "x": 320, "y": 180, "button": "left", "clicks": 1, "wait_before": null
    },
    {
      "id": "a2", "type": "wait_image", "enabled": true, "note": "Menu is open",
      "image": "images/img_menu_open.png", "region": null, "confidence": null,
      "timeout": 10, "after_found": 1, "stable_for": 0, "wait_before": null
    }
  ],
  "per_row": [
    {
      "type": "group", "id": "g1", "name": "Fill vendor info", "collapsed": false, "enabled": true,
      "items": [
        {
          "id": "b1", "type": "click", "enabled": true, "note": "Vendor field",
          "x": 500, "y": 220, "button": "left", "clicks": 1, "wait_before": null,
          "guard": {
            "image": "images/img_form_open.png", "region": null,
            "confidence": null, "timeout": 10, "after_found": 0
          }
        },
        {
          "id": "b2", "type": "type_text", "enabled": true, "note": "",
          "text": "{Vendor}", "mode": "paste", "select_all_first": false, "wait_before": null
        },
        {
          "id": "b3", "type": "key", "enabled": true, "note": "Next field",
          "keys": "tab", "repeat": 1, "wait_before": 0.4
        },
        {
          "id": "b4", "type": "type_text", "enabled": true, "note": "",
          "text": "{Amount}", "mode": "paste", "select_all_first": false, "wait_before": null
        }
      ]
    },
    {
      "id": "b5", "type": "click_image", "enabled": true, "note": "Save",
      "image": "images/img_save.png", "region": null, "confidence": null,
      "timeout": 10, "offset_x": 0, "offset_y": 0, "button": "left", "clicks": 1,
      "after_found": 0, "wait_before": null
    },
    {
      "id": "b6", "type": "wait_image", "enabled": true, "note": "Saved message",
      "image": "images/img_saved_ok.png", "region": [600, 100, 700, 200], "confidence": null,
      "timeout": 15, "after_found": 3, "stable_for": 0.5, "wait_before": null
    },
    {
      "id": "b7", "type": "wait_image_gone", "enabled": true, "note": "Spinner gone",
      "image": "images/img_spinner.png", "region": null, "confidence": null,
      "timeout": 30, "appear_grace": 1, "after_gone": 0.5, "wait_before": null
    }
  ],
  "cleanup": [
    {
      "id": "c1", "type": "key", "enabled": true, "note": "Close form",
      "keys": "esc", "repeat": 1, "wait_before": null
    }
  ]
}
```

## 부록 B. 결과 CSV 예시

```csv
run_id,row_number,row_hash,status,failed_step_id,failed_step_label,reason,screenshot,started_at,finished_at,duration_sec,macro_name,macro_version_hash,speed
20261003-0930,2,9c1f..,Done,,,,,2026-10-03T09:30:05+02:00,2026-10-03T09:30:21+02:00,16.2,Invoice Entry,a41e..,Normal
20261003-0930,3,77aa..,Done,,,,,2026-10-03T09:30:21+02:00,2026-10-03T09:30:37+02:00,15.9,Invoice Entry,a41e..,Normal
20261003-0930,4,e02d..,Failed,b6,"Wait for image: Saved message","Image not found within 15 s (best match 71%)",20261003-0930_row4_stepb6.png,2026-10-03T09:30:37+02:00,2026-10-03T09:30:55+02:00,18.0,Invoice Entry,a41e..,Normal
```

## 부록 C. 용어집

| 용어 | 의미 |
|---|---|
| Macro | 하나의 `.swm` 파일. 3구역의 동작 목록 |
| Section | Setup / Per Row / Cleanup |
| Action (Step) | 동작 한 줄 |
| Group | 동작을 묶은 접을 수 있는 폴더(1단계) |
| Guard | 동작 **전에** 확인하는 이미지 조건 |
| Verify | 동작 **후에** 확인하는 이미지 조건 |
| After found | 이미지가 나타난 뒤 추가로 기다리는 시간 |
| Region | 이미지를 검색할 화면 영역 |
| Confidence | 이미지 일치율 임계값 |
| Speed | 실행 시 모든 동작의 wait_before에 더하는 전체 지연 (Normal/Slow/Very slow) |
| Pre-flight | 실행 전 자동 검사 |
| Row | 데이터 표의 한 행 (Per Row 구역이 한 번 실행되는 단위) |
| Status | 행의 실행 상태 (Pending/Done/Failed/Interrupted/Skipped) |
| Capture helper | F8(좌표)/F9(이미지 영역) 캡처 기능 |
| Floating panel | 실행 중 표시되는 작은 상태 패널 |
