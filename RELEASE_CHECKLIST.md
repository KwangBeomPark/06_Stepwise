# Stepwise 사용자 릴리즈 체크리스트

2026-10-09 릴리스 준비 수정·검수. 배포 계약·검사를 수정하고 격리 검사와 미서명 빌드를 실행했습니다. 실제 사용자 설정·기존 공식 파일은 유지했으며 KSP 서명·설치·게시·태그 생성·커밋은 실행하지 않았습니다.

## 현재 판정 — 서명 실행 전 해결

현재는 설치 EXE `App06_Stepwise_Setup_v<version>.exe` 하나와 `build-manifest.v<version>.json`, `SHA256SUMS.v<version>.txt`의 **3개 공식 파일** 계약입니다. 설치 별칭/포터블 ZIP은 생성하지 않습니다. 설치 AppId·Stepwise.exe·설치 폴더·UserSetting은 유지합니다. 소스 버전은 **0.3.1**이며 로컬/원격 v0.3.1 태그 부재를 읽기 조회로 확인했습니다. 게시 시점에 다시 확인합니다.

- [x] 버전별 장부로 기존 generic 장부와 새 버전 충돌을 해결했습니다. 기존 generic 단일 설치 계약은 버전·커밋·지문·실제 서명·체크섬을 확인하는 읽기 호환만 제공합니다. 불완전한 버전별 장부를 generic으로 숨기지 않습니다.
- [x] 단일 설치 계약의 현재 회귀를 검수했습니다. Python **133개**, PowerShell discovery **5**, pipeline **30**, orchestration **16**, backup **34** 검사 통과. 서명 객체·compiler는 fixture에서 모킹했으며 실제 인증서 서명 성공을 뜻하지 않습니다.
- [x] 생성/서명/helper/설치 정의를 새 이름에 맞추고 소스 0.3.1로 준비했습니다. 기존 공개 0.3.0·공식 파일·태그는 보존합니다.

위 항목은 소스·자동 검수 완료입니다. 현재 소스는 미커밋이라 검수 빌드는 공식 서명 대상이 아닙니다. 아래 승인 커밋 확정·재빌드·사용자 서명·실제 설치 게이트는 남아 있습니다. 삭제 후보 선택은 사용자 검토 후입니다.

## 삭제 후보 — 사용자 검토 전 보존


용량은 조사 시점 파일 합계(byte), Git 추적 수는 모두 0입니다. 재빌드는 가능하더라도 동일 바이트 재현을 보장하지 않습니다.

| 절대 경로 | 파일 수 / byte | 역할·참조 | 재생성·삭제 조건 |
| --- | ---: | --- | --- |
| `C:\Dev\GitHub\06_Stepwise\.pytest_cache` | 5 / 10,550 | pytest 실행 캐시 | 다음 검사 때 생성. 검사가 끝났고 과거 실패 목록이 불필요하면 후보 |
| `C:\Dev\GitHub\06_Stepwise\.ruff_cache` | 21 / 10,122 | Ruff 캐시 | 다음 검사 때 생성. 실행 중 검사 도구가 없으면 후보 |
| `C:\Dev\GitHub\06_Stepwise\dist` | 227 / 262,946,698 | 과거 앱 번들. 현재 `scripts/build.ps1`은 고유 `build/unsigned` 사용 | 재빌드 가능. 개인 설정·수동 실행본·배포 검증 입력이 없는지 확인 후 후보 |
| `C:\Dev\GitHub\06_Stepwise\build\stepwise` | 16 / 18,758,617 | 과거 PyInstaller 작업 캐시 | 현재 빌드에 필수 입력 아님. 새 빌드 성공·사용 중 프로세스 없음 확인 후 후보 |
| `C:\Dev\GitHub\06_Stepwise\build\backup-test-35d898d839184eb094028ce0ab9c35f1` | 27 / 14,311 | 공통 백업 실패주입 fixture | 테스트로 재생성. 검수 결과 요약 보존 후 후보 |
| `C:\Dev\GitHub\06_Stepwise\build\backup-test-40ac79125889497c851af28a20157e24` | 27 / 14,297 | 동일 | 동일 |
| `C:\Dev\GitHub\06_Stepwise\build\backup-test-7882efb272014d8196b57f871cfd2196` | 24 / 10,996 | 동일 | 동일 |
| `C:\Dev\GitHub\06_Stepwise\build\backup-test-f221ad1a6daf463a9a6b77982f979dcf` | 24 / 10,997 | 동일 | 동일 |
| `C:\Dev\GitHub\06_Stepwise\build\installer-review-87d67d190cda4b4f8a7d6493599d8b59` | 3 / 4,707,870 | 이전 더미 설치 컴파일 fixture | 실제 사용자 설치본 아님. 컴파일 결과 기록 보존 후 후보 |
| `C:\Dev\GitHub\06_Stepwise\build\standardization\inno-36c3ba1503f84ef890228472ec9cd0ec` | 3 / 2,359,145 | canonical 설치 fixture | 재컴파일 가능. 검수 증거 보존 후 후보 |
| `C:\Dev\GitHub\06_Stepwise\build\standardization\inno-39524eb5eb8247ccb6ce9b092370abe7` | 3 / 2,357,047 | 호환 wrapper 설치 fixture | 동일 |
| `C:\Dev\GitHub\06_Stepwise\build\standardization\portable-signature-6b98a366e6b8426a8831a0f846ebda06` | 1 / 5,704,751 | 기존 ZIP 내부 서명 검수용 추출본 | 원본 ZIP에서 추출 가능. 원본 release 보존·검수 결과 기록 후 후보 |

기본 보존: `release/`, `.venv/`, `tools/`, `installer/stepwise.iss` 호환 wrapper, `build/standardization`의 해시 기준·Gemini 응답·검수 요약. `macros/`, `custom_macros/`, `images/`, `results/`는 사용자 자료일 수 있어 삭제 대상으로 삼지 않습니다. 현재 앞 세 폴더는 비어 있고 `results/`는 2개/18,563 byte지만 이름만으로 생성 목적을 단정하지 않았습니다. 외부 사용자 지정 매크로·결과·원본 Excel/CSV도 보존합니다.

## 사용자 서명·설치·게시 작업

- [ ] 현재 소스/문서의 변경을 검수하고 사용하지 않은 새 버전·릴리즈 노트·clean 검수 커밋을 확정합니다. 실제 서명 출처와 게시 태그의 커밋이 같아야 합니다.
- [ ] 앱·매크로·DB/결과 작업을 종료하고 [자료 백업](docs/USER_DATA.md)의 전체 UserSetting을 백업·검증합니다. 외부 매크로·결과·Excel/CSV·이미지는 별도 보관합니다.
- [ ] 유효한 Microsoft SignTool·Inno·의존성을 준비하고 SimplySign의 로그인·PIN/OTP·인증서 선택은 사용자 직접 관리 세션에서 처리합니다.
- [ ] 선행 승격/회귀/이름 게이트가 해결된 소스로 새 unsigned 빌드를 만들고 반환된 고유 경로를 기록합니다.

```powershell
.\scripts\build.ps1
$BuildRoot = 'C:\Dev\GitHub\06_Stepwise\build\unsigned\<실제 빌드 ID>'
.\scripts\sign.ps1 -BuildRoot $BuildRoot -CertificateThumbprint $env:STEPWISE_SIGNING_THUMBPRINT
```

- [ ] 앱 내부 Stepwise.exe와 설치 EXE의 실제 서명·게시자·타임스탬프, 빌드 출처/검사·manifest/checksum·파일 크기/hash를 확인합니다. 현재는 공식 포터블 ZIP을 생성하지 않습니다. 서명/검증 staging은 보존합니다.
- [ ] 격리 Windows에서 구버전 실행 중 종료/차단, 매크로 중단·결과 경로, 설치 실패/취소·사용자 지정 경로, 제거 후 UserSetting·외부 자료 보존과 실제 대표 화면을 확인합니다. offscreen 테스트는 실제 DPI/포커스/키보드 자동화 시험이 아닙니다. 현재 Inno는 설치 EXE를 컴파일 후 서명하며 SignedUninstaller 콜백은 없으므로 설치된 제거 프로그램의 서명/Windows 실행 정책을 별도로 확인합니다.
- [ ] 다음은 현 helper의 검증/게시 인자입니다. 실제 새 서명 세트에 사용하며 검증이 반환한 3개 파일만 게시합니다.

```powershell
$Version = '<실제 검수 완료한 다음 버전>'
$Commit = (git rev-parse HEAD).Trim()
$Thumbprint = $env:STEPWISE_SIGNING_THUMBPRINT
. .\scripts\release_helpers.ps1
$ReleaseRoot = (Resolve-Path .\release).Path
$Names = @(Assert-ReleaseArtifacts $ReleaseRoot $Version $Commit $Thumbprint)
```

- [ ] 원격 v<version> 태그가 같은 승인 커밋인지 확인합니다. 기존 helper의 즉시 공개 옵션 `-Publish`는 사용하지 않고 아래 명시 저장소·draft 절차로 진행합니다. 같은 태그의 기존 릴리스가 있으면 중단해 비교하며 기존 태그/asset을 이동·삭제·덮어쓰지 않습니다.

```powershell
$Repo = 'KwangBeomPark/06_Stepwise'
$ErrorActionPreference = 'Stop'
$Origin = (git remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $Origin -notin @("https://github.com/$Repo.git", "git@github.com:$Repo.git")) { throw 'Unexpected origin repository.' }
$Status = @(git status --porcelain)
if ($LASTEXITCODE -ne 0 -or $Status.Count) { throw 'Use the approved clean source.' }
$Branch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $Branch -ne 'main') { throw 'Use the approved main branch.' }
$CurrentCommit = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $CurrentCommit -ne $Commit) { throw 'Source commit changed after local verification.' }
$Names = @(Assert-ReleaseArtifacts $ReleaseRoot $Version $Commit $Thumbprint)
$Tag = "v$Version"
$RemoteRef = gh api "repos/$Repo/git/ref/tags/$Tag" | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Prepare the reviewed remote tag first; do not move an old tag.' }
$Object = $RemoteRef.object
while ($Object.type -eq 'tag') {
  $TagObject = gh api "repos/$Repo/git/tags/$($Object.sha)" | ConvertFrom-Json
  if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve annotated remote tag.' }
  $Object = $TagObject.object
}
if ($Object.type -ne 'commit' -or $Object.sha -ne $Commit) { throw 'Remote tag differs from the signed source commit.' }
$Files = @(
  "release\App06_Stepwise_Setup_v$Version.exe",
  "release\build-manifest.v$Version.json",
  "release\SHA256SUMS.v$Version.txt"
)
gh release create $Tag @Files --repo $Repo --verify-tag --draft --title "Stepwise $Tag" --generate-notes
if ($LASTEXITCODE -ne 0) { throw 'Draft creation failed; existing assets were not overwritten.' }

$DownloadRoot = Join-Path $PWD ('build\remote-check-' + [guid]::NewGuid().ToString('N'))
gh release download $Tag --repo $Repo --dir $DownloadRoot
if ($LASTEXITCODE -ne 0) { throw 'Cannot download the draft.' }
$ExpectedNames = @($Files | ForEach-Object { Split-Path -Leaf $_ })
if (@(Compare-Object ($ExpectedNames | Sort-Object) (@(Get-ChildItem -LiteralPath $DownloadRoot -File).Name | Sort-Object)).Count) { throw 'Unexpected remote asset set.' }
foreach ($File in $Files) {
  if ((Get-FileHash -LiteralPath $File).Hash -ne (Get-FileHash -LiteralPath (Join-Path $DownloadRoot (Split-Path -Leaf $File))).Hash) { throw 'Remote bytes differ from the verified local set.' }
}
Assert-ReleaseArtifacts $DownloadRoot $Version $Commit $Thumbprint
# 실제 Windows 설치·제거 합격과 사용자 최종 검토 후 공개
gh release edit $Tag --repo $Repo --draft=false --verify-tag --latest
if ($LASTEXITCODE -ne 0) { throw 'Publication failed; do not report completion.' }
```

- [ ] 공개 후 새 빈 폴더에 다운로드해 이름·개수·크기·SHA-256·서명을 확인합니다. 기존 태그/asset을 지우거나 --clobber로 덮어쓰지 않습니다. 완료 여부는 실제 로그로 기록합니다.

[설치 합격표](docs/INSTALL_UPGRADE_ACCEPTANCE.md) · [이번 전체 재검토](../04_DataRefinery/docs/CLEANUP_AND_RELEASE_REVIEW.md)

## Gemini/검수 경계

10월 8일 요청의 빈 response·0토큰은 미완료였습니다. 이번 10월 9일 Gemini 3.8 Flash High/effort high 계약 검토는 **54.54초, 내용 있는 SUCCESS**, conversation `229c6169-5f07-48fe-8bcc-251b0cebcf51`입니다. 원격/교차 볼륨 지적은 실제 승격 임시 파일이 목적지와 같은 디렉터리에 생성되므로 적용하지 않았고 경합·권한/실패 검수는 반영했습니다. CLI 보고 사용량 28,407토큰이며 크레딧 차감은 확인하지 않았습니다.

실제 미서명 앱 빌드: `build/unsigned/ae22b3f8be43482491bc52703130ffa7`, exit 0, `source_dirty=true`. 전체 앱 번들로 Inno도 컴파일했습니다: `build/standardization/installer-prep-e253a6cd0ecd404d9e979db421c2ec53/App06_Stepwise_Setup_v0.3.1.exe`, 파일 버전 0.3.1, 서명 NotSigned. 검사·빌드 로그는 `build/standardization/signing-preparation-build.log`, 요약은 `build/standardization/signing-preparation-result.json`입니다. 승인 커밋 후 다시 빌드해야 하며 이 경로를 곧바로 서명에 재사용하지 않습니다. 실제 서명·Windows 설치·게시 성공은 미검증입니다.
