# Stepwise (스텝와이즈)

**Windows 업무 환경을 위한 데이터 기반 매크로 자동화 도구**

Stepwise는 사내 ERP(SAP 등), 웹 포털, 사내 전용 프로그램에 Excel 및 CSV 데이터 표의 값을 반복 입력하고 클릭하는 작업을 안전하게 자동화하는 데스크톱 도구입니다.

---

## 주요 특징

- **3구역 명확한 구조**: **Setup**(초기 설정 1회), **Per Row**(데이터 행별 반복), **Cleanup**(마무리 1회)의 직관적인 위-아래 순차 실행.
- **데이터 기반 자동화**: `.xlsx`, `.csv` 파일을 연결하고 텍스트에 `{열이름}` 변수를 삽입하여 대량의 데이터를 순차 입력.
- **철저한 안전 우선 원칙**: 이미지 타임아웃이나 오류 발생 시 **즉시 중지**. 오입력이나 중복 저장을 유발하는 무분별한 자동 재시도 방지.
- **Guard & Verify 이미지 안전장치**: 동작 실행 전 상태를 확인하는 Guard, 실행 후 결과 화면을 확인하는 Verify 제공.
- **원클릭 Speed 지연 조절**: ERP가 느린 날에도 매크로 수정 없이 **Normal**, **Slow(+0.5s)**, **Very slow(+1.0s)** 로 전체 속도 조절 가능.
- **관리자 권한 불필요**: 사용자 로컬 디렉터리에 설치되어 사내 IT 관리자 권한 없이 즉시 실행 가능.
- **F12 비상 정지**: 실행 중 또는 대기 중 언제든지 즉시 중단.
- **결과 CSV 및 이어서 실행**: 원본 데이터를 보존하며 별도 결과 CSV에 행별 상태를 실시간 기록하고 중단 지점부터 즉시 재개.

---

## 실행 방법

### 개발 환경 실행
```cmd
# 1. 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate

# 2. 의존 패키지 설치
pip install -r requirements.txt

# 3. 앱 실행
python -m stepwise
```

또는 루트 폴더의 `run_app.bat`을 더블클릭하여 바로 실행할 수 있습니다.

---

## 테스트 실행
```cmd
.venv\Scripts\pytest
```

---

## 관련 문서
- [stepwise-dev-guide.md](stepwise-dev-guide.md): 설계 명세서 및 개발 가이드
- [AI_CODE_MAP.md](AI_CODE_MAP.md): 아키텍처 및 모듈 맵
- [myAGENT.md](myAGENT.md): 개발 원칙 및 사내 레지스트리 가이드
