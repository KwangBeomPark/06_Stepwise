# 3–5단계 설정·구조·문구 검수

검수일: 2026-10-08. 이전 단계의 미커밋 변경과 공식 배포물을 보존했습니다.

## 변경과 보존 계약

- 사용자 저장 값은 기본값보다 우선합니다. 저장은 고유 임시 파일에 flush/fsync 후 원자 교체하며, 실패는 호출자에게 전달합니다. 쓰기 가능 검사도 기존 `.write_probe` 파일을 덮어쓰지 않습니다.
- 손상 JSON·잘못된 UTF-8·객체가 아닌 기존 설정은 저장 전과 교체 직전에 검증합니다. 시작 시 기본값으로 동작하더라도 창 종료의 레이아웃 저장으로 원본을 덮어쓰지 않으며 OSError로 안내합니다. 자동 복구·스키마 변경은 하지 않습니다.
- 설정 창은 저장 성공 후에만 값을 적용하고 닫습니다. 실패하면 기존 값을 유지하고 사용자에게 안내합니다.
- 기존 결과 폴더 설정이 실행 경로에 전달되지 않는 문제를 수정했습니다. GUI 전검사·실행 snapshot·worker와 CLI가 같은 결과 위치를 사용합니다. CLI `--results-dir`는 저장 값보다 우선합니다.
- 파일 로그를 생성하지 않는 실제 동작에 맞춰 `Open Logs Folder`를 `Open Results Folder`로 바꿨습니다. 기본 설정·매크로·결과는 `UserSetting`에 있으며 외부 사용자 지정 폴더와 원본 Excel/CSV는 별도 백업 범위입니다.
- `installer/setup.iss`가 유일한 설치 정의이며 `stepwise.iss`는 호환 include입니다. 기존 AppId 원문·설치 경로·UserSetting 보존·실행 중 파일 안전 차단 정책을 유지했습니다.
- 이전 `release/build/signtool` 탐색을 제거했습니다. 기존 도구 파일은 삭제하지 않았습니다.
- [공개 코드 지도](CODE_MAP.md), README 두 언어, 설치 요청 문서와 로컬 개인 지도를 실제 구조에 맞췄습니다. 개인 지도는 추적하지 않습니다.
- [공통 백업 도구](../scripts/Manage-UserData.ps1)·[사용자 자료 계약](USER_DATA.md)은 총괄 담당자가 제공했습니다. 기본 전체 백업, `-SettingsOnly` 결과 제외, 외부 자료 별도 보존이며 빌드 게이트에 백업 회귀를 연결했습니다.

## 자동 검수 근거

- `.venv` Python + `QT_QPA_PLATFORM=offscreen`: 최종 전체 pytest **133개 통과**, 프로세스 exit 0. 불규칙 종료 문제 수정 후 손상 JSON 검수 추가 전 전체 128개를 추가 3회 연속 통과했습니다.
- 새로운 설정 안전성 검수 14개: 사용자 0 값/외부 경로 우선, 교체·fsync 실패 시 원본과 임시 파일 보호, 기존 probe 보호, GUI 실패 전달, 실제 결과 위치 전검사·CLI 전달, 손상 원본·창 종료 저장·임시 파일 작성 후 외부 손상 발생 보호. 기존 snapshot 검수도 실행 후 설정 변경에 영향받지 않음을 확인합니다.
- Windows PowerShell 5: 도구 탐색 5, 배포 안전성 실패주입 26, 모의 orchestration 13, 공통 백업 34 — **78 assertions**. 실제 서명·게시를 하지 않습니다.
- 변경 Python의 프로젝트 Ruff 규칙, PowerShell 파싱, `git diff --check` 통과.
- 실제 Inno Setup 6: canonical과 호환 wrapper 각각 소유한 `build/standardization/inno-*/output`에 더미 EXE fixture를 컴파일했습니다. 두 컴파일 성공은 설치 실행 증거가 아닙니다. CLI fixture 버전 0.9.99를 사용했으며 제품 버전 0.3.0은 변경하지 않았습니다.
- 공식 `release/` 파일 **5개**의 개수와 SHA-256이 검수 전 기준과 같습니다. `build/standardization/release-baseline.json`에 기준을 남겼습니다.

실제 Windows Qt 플러그인 검수에서 기존 테스트만 실행해도 Python 종료 시 `0xC0000409`가 발생했고 화면 포커스 테스트가 활성 창 상태에 영향을 받았습니다. 테스트 소유 Qt 창을 QApplication이 살아 있을 때 폐기하는 fixture를 추가했습니다. 자동 검수는 offscreen으로 수행했으며, 실제 화면 입력·설치·업그레이드·제거는 별도 수동 게이트입니다.

## Gemini 사용과 독립 검수

Antigravity CLI `gemini-3.8-flash-high`, effort `high`에 작은 도구 없는 설정 저장·문구 검수 요청을 보냈습니다. 실제 내용이 있는 SUCCESS 응답 1회, 경과 107.167초(모델 기록 101.850초), conversation `04bcf111-2b3a-40a9-b670-c500bf4f3afb`입니다. 증거는 무시되는 `build/standardization/agy-phase3-5.json`에 있습니다. 입력 22,887·출력 10,098·합계 32,985 토큰으로, 토큰 절약을 확인했다는 주장은 하지 않습니다.

응답의 존재하지 않는 `_collect_ui_settings`, 잘못된 저장 함수 인자, 구현 없는 진단 버튼 및 설정만 백업한다는 문구는 채택하지 않았습니다. 실제 저장 API·결과 폴더 기능·전체 백업 계약에 맞춰 수정한 뒤 위 검수를 수행했습니다. 권한 우회나 전역 설정 변경은 하지 않았습니다.

## 남은 실제 게이트

사용자 서명 세션, 새 공식 서명물 생성, GitHub 게시, 원본 데이터의 화면 자동화 및 실제 설치·실행 중 구버전 교체는 수행하지 않았습니다. 기존 공식 파일을 덮어쓰거나 사용자 자료를 삭제하지 않았습니다.
