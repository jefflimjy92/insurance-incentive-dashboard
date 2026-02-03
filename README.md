# 💰 VIBE 인센티브 대시보드 v1

보험 설계사의 시상 인센티브를 자동 계산하고 시각화하는 대시보드입니다.

## 🚀 주요 기능
- **시상 자동 계산**: 정률형, 계단형, 연속형 등 복합 시상 최적 계산
- **경쟁 시상 처리**: 중복 시상 중 가장 높은 금액 자동 선택
- **실시간 데이터 연동**: Google Sheets 또는 CSV 업로드 지원
- **KST 시간 반영**: 조회 시점의 한국 표준시 자동 표시

## 📁 폴더 구조
- `streamlit_app.py`: 메인 대시보드 앱
- `data_loader.py`: 데이터 로딩 및 전처리 모듈
- `incentive_engine.py`: 시상 계산 핵심 엔진
- `ui_components.py`: UI 컴포넌트 라이브러리
- `analysis.py`: 설계사 및 지점 성과 분석
- `sample_data/`: 테스트용 샘플 데이터

## 🛠 실행 방법
1. 필수 패키지 설치:
   ```bash
   pip install -r requirements.txt
   ```
2. 앱 실행:
   ```bash
   streamlit run streamlit_app.py
   ```
