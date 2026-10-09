# Stepwise 공개 코드 지도

Stepwise는 Excel/CSV 행을 화면의 클릭·입력·이미지 확인 단계에 연결하는 자동화 도구입니다.
SwiftDeck의 단축 명령·텍스트 확장과 별도 앱이며, 원본 데이터 파일을 수정하지 않습니다.

| 경로 | 역할·계약 |
| --- | --- |
| `src/stepwise/app.py`, `cli.py` | Qt 앱·CLI 진입점. CLI의 `--results-dir` → 저장된 결과 폴더 → 앱 기본값 순 |
| `src/stepwise/core/app_paths.py` | 설치·포터블 설정 위치, 사용자 설정 우선순위, 손상 원본 덮어쓰기 차단, 고유 임시 파일→flush/fsync→교체→실패 전달 |
| `src/stepwise/core/` | 매크로 모델·스키마·패키지·변수. OS 입력·UI에 의존하지 않는 모델 |
| `src/stepwise/services/` | Windows 입력·화면·클립보드·핫키·이미지 비교·파일 잠금 |
| `src/stepwise/engine/` | 행별 실행·취소 가능한 대기·원본 보존·결과 CSV·실패 이미지 |
| `src/stepwise/ui/main_window.py` | 실행 전 설정·데이터의 snapshot을 worker로 전달. 설정 결과 폴더를 preflight와 worker에 동일하게 전달 |
| `src/stepwise/ui/settings_dialog.py`, `strings.py` | 저장 실패 시 창 유지·경고, 실제 설정/결과 폴더·백업 범위 안내. 사용자 문구는 영어 |
| `installer/setup.iss` | 유일한 설치 정의. 기존 AppId·경로·설정 보존, busy EXE 교체 차단 |
| `installer/stepwise.iss` | 기존 호출을 유지하는 `setup.iss` include wrapper |
| `installer/stepwise.spec` | PyInstaller 번들 정의 |
| `scripts/build.ps1` | unsigned 고유 build 폴더·테스트 및 빌드 출처 기록 |
| `scripts/sign.ps1`, `release_helpers.ps1` | 앱→설치 EXE 한 개 서명, 버전별 장부로 기존 generic 장부 보호. staging→검증→새 공식 버전 추가. 게시 별도 opt-in, 과거 generic 단일 설치 계약은 검증 읽기 호환 |
| `tests/` | 사용자 설정 환경과 작업 디렉터리를 임시 폴더로 격리한 pytest·PowerShell 실패주입 |

일반 설정은 실행 폴더의 쓰기 가능한 `UserSetting` 또는 `%LOCALAPPDATA%/Programs/Stepwise/UserSetting`에 있습니다.
기본 매크로·결과는 그 아래 `macros`·`results`입니다. 사용자 지정 외부 폴더와 원본 Excel/CSV는 별도 보존 범위입니다.
설정 UI의 결과 폴더 버튼은 실제 선택된 위치를 엽니다. 현재 별도 파일 로그 writer는 없으며 결과 CSV·실패 이미지가 진단 자료입니다.

[백업·검증 복원](USER_DATA.md), [공통 백업 도구](../scripts/Manage-UserData.ps1),
[3–5단계 검수](STANDARDIZATION_PHASE3_5_REVIEW.md), [공통 정비 기준](SUITE_STANDARDIZATION.md)을 함께 확인하세요.
로컬의 `AI_CODE_MAP.md`와 개인 작업 지침은 공개 추적 대상으로 추가하지 않습니다.
