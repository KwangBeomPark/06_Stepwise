# Stepwise 배포 정비 2단계 검수

검수일: 2026-10-07. 소스 버전 0.3.0 유지. 실제 인증서 서명·설치·GitHub 게시를 실행하지 않았습니다.

## 변경 결과

- `scripts/build.ps1`은 고유 `build/unsigned/<id>`에서 전체 Python 테스트와 배포 PowerShell 회귀를 실행한 다음 unsigned bundle을 만듭니다. `build-input.json`은 커밋, dirty 여부, 파일 목록·해시, 테스트 성공·검사 로그 해시를 기록합니다. 기존 build/dist/release를 지우지 않습니다.
- `scripts/sign.ps1 -BuildRoot ... -CertificateThumbprint ...`은 테스트 근거가 있으며 현재 clean commit과 같은 빌드만 받습니다. 앱 서명→ZIP·설치 생성→설치 파일 한 번 서명→별칭 복사→ZIP 내부 EXE·인스톨러 서명과 해시 검증→공식 폴더 반영 순서입니다. 인증서 지문은 명시 인자 또는 `STEPWISE_SIGNING_THUMBPRINT`로 전달하며 사용자 서명 세션을 사용합니다.
- 공식 결과는 기존 이름의 설치 두 개와 포터블 ZIP, `build-manifest.v<version>.json`, `SHA256SUMS.v<version>.txt`입니다. 기존 버전, generic manifest/checksum은 유지합니다. 같은 버전의 다른 내용은 거부하며 동일 내용의 기존 파일도 다시 쓰지 않습니다.
- 새 파일은 고유 임시 파일에서 해시를 확인하고 기존 파일을 대체하지 않는 이동으로 반영합니다. 실패·변경 감지 시 이번 실행이 추가한 파일만 되돌립니다. 파일 시스템 장애로 되돌리기까지 실패하면 오류를 전달하며 기존 공식 파일은 건드리지 않습니다. 여러 파일의 반영 전체가 전원 장애까지 원자적인 거래라고 주장하지 않습니다.
- 게시 기본값은 꺼짐입니다. 명시 `-Publish`에서 기존 원격 태그의 커밋을 확인하고 이미 있는 자산을 실제 다운로드해 로컬 해시와 비교한 뒤 누락 자산만 올립니다. 태그 이동·기존 자산 덮어쓰기·삭제는 하지 않습니다. 게시 후 자산 바이트를 재확인합니다.

## 설치·업그레이드

두 ISS의 기존 AppId literal `{{C782B3E1-628D-4C10-9E1D-3A20B71E86E2}}`을 그대로 보존했습니다. 이전 설치 경로 재사용을 명시하고, Restart Manager 정상 종료 요청은 유지하며 자동 재시작은 끕니다. 첫 `[Files]` 항목 실행 직전 `BeforeInstall`에서 기존 `Stepwise.exe`의 배타적 쓰기 열기를 확인합니다. 정상 종료되지 않았거나 파일이 잠겼으면 복사 전에 오류를 내며 강제 종료하지 않습니다. 이 검사는 프로세스 목록 전체나 시작 경합을 완전히 증명하는 검사가 아닙니다.

고정 이름 EXE를 교체하므로 앱 전체 선제 제거는 하지 않습니다. 설치 파일에 `UserSetting`, 루트 `macros`, `results`를 넣지 않으며 설정·매크로·결과를 삭제하는 규칙은 추가하지 않았습니다. 기존 앱의 `closeEvent`는 실행 중 매크로의 중단을 요청하고 worker 완료 후 닫습니다. Windows Restart Manager와 실제 앱의 종료·거부 상호작용은 실제 설치 게이트로 남습니다.

근거: [Inno CloseApplications](https://jrsoftware.org/ishelp/topic_setup_closeapplications.htm), [RestartApplications](https://jrsoftware.org/ishelp/topic_setup_restartapplications.htm), [event callbacks](https://jrsoftware.org/ishelp/topic_scriptevents.htm). `PrepareToInstall`은 Restart Manager 확인 전이므로 첫 파일의 `BeforeInstall` 검사를 사용했습니다.

## 자동 검증

- 전체 `pytest tests -q`: 119개 통과. 수집 목록 합계로 개수를 확인했습니다.
- `Test-ReleasePipeline.ps1`: 26개 assertion. 입력 변경, 미서명·다른 서명자, ZIP 내부 미서명, 잘못된 버전·커밋, 별칭·체크섬 변경, 중간 반영 실패·변조, 기존 공식 파일·generic metadata 보존, 경로 이탈, 원격 자산 불일치·태그 불일치·누락만 업로드를 격리 fixture로 검사했습니다.
- `Test-ReleaseOrchestration.ps1`: 13개 assertion. 실제 sign entrypoint를 복사한 fixture에서 모의 signer/compiler를 써 앱 먼저·설치 한 번 서명, 별칭 동일, unsigned 원본 보존, 컴파일 실패 보호, 테스트 실패·커밋 불일치·로그 변경의 서명 전 차단을 검사했습니다.
- `Test-SignToolDiscovery.ps1`: 5개 assertion. 개인 경로 없는 도구 탐색을 확인했습니다.
- PowerShell 5.1 파싱 및 `git diff --check` 통과.
- Inno Setup 6.7.3: 두 ISS 모두 고유 `build/installer-review-<id>`의 더미 EXE 입력으로 컴파일 성공. 이 파일은 unsigned 검수 fixture이며 설치·실배포 파일이 아닙니다. 공식 `release/` 출력은 없습니다.

실제 서명 검증은 모의 테스트로 대체한 것으로 구분합니다. 실제 인증서·포터블 서명, 사용 중 업그레이드·거부·실패·취소, 사용자 지정 설치 경로, 제거 후 자료 보존, GitHub 게시·다운로드 검증은 아직 실행하지 않았습니다.

## 에이전트 검수

Antigravity CLI의 `gemini-3.8-flash-high --effort high`에 설계와 실패 검수 요구를 전달했습니다. 첫 설계 응답의 서명 순서·모듈 분리·테스트 제안을 활용했습니다. 전체 공식 release 디렉터리 교체·삭제 제안은 보존 계약에 맞지 않아 기각했습니다. 후속 코드 검수(180초)와 변조 실패 테스트 코드 요청(90초)은 응답 없이 시간 제한으로 종료돼 통과 근거에 포함하지 않았습니다. Codex 독립 구현·실행 검수 및 SwiftDeck 담당의 교차 검수에서 테스트 출처·출력 reparse 보호·별칭 이름 기준 비교를 보완했습니다.
