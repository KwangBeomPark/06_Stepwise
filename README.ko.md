*다른 언어로 읽기: [한국어](README.ko.md), [English](README.md) | 📖 **사용자 매뉴얼**: [한국어 매뉴얼](docs/manual/USER_MANUAL.ko.md) · [English Manual](docs/manual/USER_MANUAL.md) · [Instrukcja Polski](docs/manual/USER_MANUAL.pl.md)*

# <img src="assets/icons/stepwise.png" width="36" height="36" valign="middle" alt="Stepwise Icon"> Stepwise (스텝와이즈)

<p align="center">
  <img src="assets/images/stepwise-hero.png" width="950" alt="Stepwise - Windows 데이터 기반 매크로 자동화 도구">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?logo=windows&logoColor=white" alt="Windows Platform">
  <img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/GUI-PySide6%20Qt-41CD52?logo=qt&logoColor=white" alt="PySide6">
  <img src="https://img.shields.io/badge/Vision-OpenCV-5C3EE8?logo=opencv&logoColor=white" alt="OpenCV">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License MIT">
  <img src="https://img.shields.io/badge/Admin%20Rights-Not%20Required-brightgreen" alt="Non-Admin">
</p>

> **사내 ERP(SAP 등) 및 사내 웹 포털의 반복 데이터 입력을 안전하고 신뢰성 있게 자동화하는 데스크톱 도구**  
> 복잡한 코드나 관리자 권한(Admin) 없이, 엑셀 표를 연결하고 시각적으로 매크로를 구성하여 바로 업무에 적용할 수 있습니다.

---

## 💡 왜 Stepwise인가요? (Why Stepwise?)

사내 업무 현장에서는 대량의 전표, 송장, 마스터 데이터를 ERP(SAP GUI 등)나 웹 시스템에 하루에도 수백 건씩 손으로 입력해야 합니다.

- **API 부재 및 개발 비용**: 레거시 ERP에 일괄 업로드 인터페이스를 구축하려면 막대한 SI 비용과 보안 승인이 필요합니다.
- **기존 무차별 매크로의 위험성**: 일반적인 키보드/마우스 매크로는 네트워크 지연이나 팝업창 발생 시 화면을 확인하지 않고 맹목적으로 클릭하여 **데이터 오입력이나 중복 저장 사고**를 유발합니다.
- **설치 및 권한 장벽**: 상용 무거운 RPA 솔루션은 비싸고 복잡하며 사내 PC에서 관리자 권한(Admin)을 요구하여 실무자가 도입하기 어렵습니다.

**Stepwise**는 이러한 실무자의 고충을 직접 해결하기 위해 개발되었습니다. 엑셀/CSV 데이터의 열 변수를 기반으로 순차 입력하며, 실행 전후 컴퓨터 비전(OpenCV)으로 화면 상태를 정밀 확인하고, 조금이라도 이상이 생기면 **즉시 정지(Fail-Fast)** 하여 기업 데이터를 안전하게 보호합니다.

---

## 🛡️ Stepwise의 4대 핵심 기둥 (Core Pillars)

<p align="center">
  <img src="assets/images/stepwise-features.png" width="950" alt="Stepwise 자동화 엔진의 4대 핵심 기둥">
</p>

### 1. 3구역 명확한 워크플로우 (3-Section Pipeline)
매크로 흐름이 복잡하게 얽히지 않도록 직관적인 3단계 구조를 제공합니다:
- **Setup (초기화 1회)**: ERP 실행, 특정 T-Code 입력, 조회 메뉴 진입
- **Per Row (행별 반복)**: 엑셀/CSV 데이터의 각 행을 읽어 `{VendorCode}`, `{Amount}` 등의 변수를 순차 입력
- **Cleanup (마무리 1회)**: 작업 요약 로그 기록 및 트랜잭션 닫기

### 2. Guard & Verify 시각 안전장치 (Computer Vision Safety)
- **Guard (사전 확인)**: 특정 입력 필드나 창이 정상적으로 열려 있는지 화면 템플릿 매칭으로 먼저 확인한 후 동작을 수행합니다.
- **Verify (사후 검증)**: 저장 버튼을 누른 후 "저장 완료" 토스트나 메시지가 화면에 떴는지 확인합니다.
- **화면 프리즈 캡처 도우미**: `F8`(좌표 즉시 지정), `F9`(화면 일시정지 후 드래그 캡처)를 통해 개발자 지식 없이도 마우스로 대상 요소를 등록합니다.

### 3. 실패 즉시 중지 및 원본 보존 (Fail-Fast & Non-Destructive)
- 화면 이상이나 타임아웃 발생 시 **무분별한 재시도나 건너뛰기 없이 즉시 실행을 중단**합니다.
- 원본 엑셀/CSV 파일은 절대 변형하지 않으며, 실시간으로 별도의 결과 CSV 파일에 행별 성공/실패 여부와 스크린샷을 기록합니다.
- 작업이 멈추더라도 결과 CSV를 바탕으로 **실패/미처리 행부터 즉시 이어서 실행(Resume)** 할 수 있습니다.

### 4. 속도 조절 & F12 비상 정지 (Speed Control & Emergency Stop)
- 사내 네트워크가 느린 날에도 매크로 수정 없이 **Normal / Slow(+0.5s) / Very slow(+1.0s)** 버튼 하나로 전체 속도를 손쉽게 제어합니다.
- 실행 중 이상 감지 시 Win32 전역 단축키 **F12**를 누르면 대기 시간 없이 0.01초 내에 즉시 모든 동작이 멈춥니다.

---

## 🖥️ 사용자 인터페이스 (Application UI)

<p align="center">
  <img src="assets/images/stepwise-app-ui.png" width="950" alt="Stepwise 사용자 인터페이스 - 직관적인 3구역 트리 및 고대비 엔터프라이즈 라이트 테마">
</p>

---

## 🚀 빠른 시작 (Quick Start)

### 1. 인스톨러로 간편 설치 (일반 사용자용)
사내 IT 관리자 권한 없이 일반 사용자 폴더(`%LOCALAPPDATA%\Programs\Stepwise`)에 설치됩니다.
- [GitHub Releases](https://github.com/KwangBeomPark/06_Stepwise/releases)에서 설치 파일을 내려받아 실행합니다.
- 바탕화면 바로가기 또는 시작 메뉴에서 `Stepwise` 실행

### 2. 소스 코드에서 바로 실행 (개발자용)
```cmd
# 1. 저장소 클론 및 가상환경 설정
git clone https://github.com/KwangBeomPark/06_Stepwise.git
cd 06_Stepwise
python -m venv .venv
.venv\Scripts\activate

# 2. 의존 패키지 설치
pip install -r requirements.txt

# 3. 앱 실행
python -m stepwise
```
*(또는 루트 폴더의 [run_app.bat](run_app.bat)을 더블클릭하면 가상환경 감지 후 자동으로 실행됩니다.)*

---

## 🧪 품질 및 검증 현황 (Quality Gates)

Stepwise는 엔터프라이즈 환경에서의 무결성과 안정성을 보장하기 위해 엄격한 사전 테스트를 거쳤습니다.

| 검증 분야 | 검증 도구 | 검증 결과 | 상세 내용 |
| :--- | :--- | :---: | :--- |
| **단위/통합 테스트** | `pytest` | **42 / 42 통과** | 모델, 변수 보간, Win32 입력, 템플릿 매칭, 러너 전원 통과 |
| **코드 스타일 & 린트** | `ruff` | **0 Warnings, 0 Errors** | PEP 8 및 최신 Python 클린 코드 컨벤션 준수 |
| **Windows 스파이크** | Win32 API | **9대 항목 통과** | DPI 배율, SendInput, 가상화면 캡처, F12 핫키 검증 완료 |
| **패키징 검증** | PyInstaller + Inno Setup | **빌드 성공** | 독립 설치 프로그램(`Stepwise-Setup-0.1.0.exe`, 71.5 MB) 생성 |

---

## 📂 프로젝트 구조

```text
06_Stepwise/
├── assets/
│   └── images/              # README 및 매뉴얼 시각 자료
├── docs/
│   ├── it-request.md        # 사내 IT 보안 승인용 화이트리스트 신청서
│   └── m0-report.md         # Windows 9대 환경 검증 기술 스파이크 보고서
├── installer/
│   ├── setup.iss            # 유일한 논어드민 설치 정의
│   ├── stepwise.iss         # setup.iss를 포함하는 호환 진입점
│   └── stepwise.spec        # PyInstaller Onedir 빌드 최적화 스펙
├── release/dist/
│   └── Stepwise-Setup-0.1.0.exe # 배포용 단일 설치 프로그램
├── src/stepwise/
│   ├── app.py / __main__.py # 앱 진입점 및 Qt 런타임
│   ├── cli.py               # 백그라운드/CLI 배치 러너
│   ├── core/                # 데이터 모델, 스키마, .swm 패키지, 변수 치환
│   ├── engine/              # 3구역 실행 러너, 8대 액션, 속도 조절, 결과 CSV 기록
│   ├── services/            # Win32 SendInput, DPI/화면 캡처, OpenCV 매칭, 핫키
│   └── ui/                  # PySide6 GUI (트리 뷰, 동적 속성창, 플로팅 패널)
├── tests/                   # pytest 단위 및 통합 테스트 슈트
├── tools/
│   ├── dummy_erp.py         # 매크로 검증용 가상 ERP GUI 시뮬레이터
│   └── spike/               # Windows 저수준 동작 검증 스파이크 스크립트
└── stepwise-dev-guide.md    # 전체 기술 설계 및 개발 가이드
```

---

## 👨‍💼 개발 배경 (Project Background)

본 도구는 전문 소프트웨어 개발사 제품이 아닌, **실제 기업 현장에서 재무/운영 실무를 담당하는 실무자의 경험**을 바탕으로 설계되고 구현되었습니다.

현업에서 가장 번거롭고 실수하기 쉬운 데이터 입력 프로세스를 정확히 진단하여, 불필요한 기능은 과감히 배제하고 **"단순함, 신뢰성, 안전성(Safety-First)"** 에 집중하여 누구나 안심하고 사용할 수 있는 도구를 지향합니다.

---

## 📄 라이선스 (License)

본 프로젝트는 [MIT License](LICENSE)에 따라 자유롭게 사용, 수정, 배포할 수 있습니다.


공통 설치·설정·배포 정비의 기준과 현재 예외는 [6개 앱 공통 정비 기준](docs/SUITE_STANDARDIZATION.md)을 참고하세요.

[공개 코드 지도](docs/CODE_MAP.md)에서 모듈과 실제 설정·결과 저장 흐름을 확인할 수 있습니다.
[백업·검증 복원 안내](docs/USER_DATA.md)와 [백업 도구](scripts/Manage-UserData.ps1)는
UserSetting 전체를 기본으로 보존하며 `-SettingsOnly`는 기본 결과 폴더를 제외합니다.
사용자 지정 외부 매크로·결과 폴더 및 원본 Excel/CSV는 별도로 백업해야 합니다.
설정 저장 실패 시 창을 닫지 않고 원래 값과 저장 파일을 보존합니다.
[설정·구조·사용 문구 검수](docs/STANDARDIZATION_PHASE3_5_REVIEW.md)를 참고하세요.

`scripts/build.ps1`은 공식 파일을 건드리지 않고 고유한 `build/unsigned` 빌드와 출처 정보를 만듭니다. 변경을 커밋하고 다시 빌드한 뒤 사용자 서명 세션에서 `scripts/sign.ps1 -BuildRoot <표시된 빌드 폴더> -CertificateThumbprint <서명 인증서 지문>`을 실행합니다. 앱 서명 후 `App06_Stepwise_Setup_v<version>.exe` 설치 파일 한 개와 `build-manifest.v<version>.json`, `SHA256SUMS.v<version>.txt`를 검증합니다. 설치 별칭·포터블 ZIP은 생성하지 않습니다. 버전별 장부를 사용해 기존 generic 장부를 보존합니다. GitHub 게시는 별도 `-Publish`와 같은 커밋을 가리키는 기존 원격 태그가 필요하며, 기존 자산을 검증한 후 누락분만 올립니다. 현재 [릴리스 체크리스트](RELEASE_CHECKLIST.md)를 참고하세요.
