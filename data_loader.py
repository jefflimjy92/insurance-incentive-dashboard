"""
데이터 로더 모듈
Google Sheets 공개 URL 및 CSV 파일 로드
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
import streamlit as st
import re


def extract_sheet_id(url: str) -> Optional[str]:
    """
    Google Sheets URL에서 스프레드시트 ID 추출
    
    Args:
        url: Google Sheets URL
    
    Returns:
        str or None: 스프레드시트 ID
    """
    # 패턴: /d/SPREADSHEET_ID/
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if match:
        return match.group(1)
    return None


def get_public_sheet_csv_url(spreadsheet_url: str, sheet_name: str) -> str:
    """
    공개 스프레드시트의 CSV 다운로드 URL 생성
    
    Args:
        spreadsheet_url: Google Sheets URL
        sheet_name: 시트 이름 (gid 대신 시트명 사용)
    
    Returns:
        str: CSV 다운로드 URL
    """
    sheet_id = extract_sheet_id(spreadsheet_url)
    if not sheet_id:
        raise ValueError("유효하지 않은 Google Sheets URL입니다.")
    
    # 시트명을 URL 인코딩
    import urllib.parse
    encoded_sheet_name = urllib.parse.quote(sheet_name)
    
    # 공개 CSV export URL (시트명 기반)
    # 형식: https://docs.google.com/spreadsheets/d/{ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
    
    return csv_url


# 캐시 비활성화 - 항상 새로운 데이터 로드
# @st.cache_data(ttl=300)
def load_public_sheet(spreadsheet_url: str, sheet_name: str) -> pd.DataFrame:
    """
    공개 Google Sheets를 DataFrame으로 로드
    
    Args:
        spreadsheet_url: 스프레드시트 URL
        sheet_name: 시트 이름
    
    Returns:
        pd.DataFrame: 데이터프레임
    """
    import ssl
    import urllib.request
    import io
    
    csv_url = get_public_sheet_csv_url(spreadsheet_url, sheet_name)
    
    try:
        # SSL 컨텍스트 생성 (인증서 검증 비활성화 - 개발용)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # URL에서 데이터 읽기
        with urllib.request.urlopen(csv_url, context=ssl_context) as response:
            csv_data = response.read().decode('utf-8')
        
        df = pd.read_csv(io.StringIO(csv_data))
        return df
    except Exception as e:
        raise ValueError(f"스프레드시트를 읽을 수 없습니다. 공개 설정을 확인하세요.\n오류: {str(e)}")

def standardize_name(name):
    """회사명 표준화"""
    if pd.isna(name): return name
    name = str(name).replace(' ', '').replace('_', '')
    if 'KB' in name: return 'KB손해보험'
    if '삼성' in name: return '삼성화재'
    if '메리츠' in name: return '메리츠화재'
    if '현대' in name: return '현대해상'
    if '한화' in name: return '한화손해보험'
    if '흥국' in name: return '흥국화재'
    if 'DB' in name: return 'DB손해보험'
    if '롯데' in name: return '롯데손해보험'
    return name


def load_contracts_from_url(spreadsheet_url: str, sheet_name: str = "계약데이터") -> pd.DataFrame:
    """
    공개 스프레드시트에서 계약 데이터 로드
    """
    df = load_public_sheet(spreadsheet_url, sheet_name)
    
    # 컬럼명 매핑 (사용자 스프레드시트 → 앱 기대 컬럼명)
    column_mapping = {
        '계약일자': '접수일',
    }
    
    df = df.rename(columns=column_mapping)
    
    # [접수일] 컬럼 표준화
    if '접수일' not in df.columns:
        for col in ['계약일자', '접수일자', '일자']:
            if col in df.columns:
                df['접수일'] = df[col]
                break
    
    # 모집인명이 없으면 사원명으로 대체
    if '모집인명' not in df.columns and '사원명' in df.columns:
        df['모집인명'] = df['사원명']
    
    # 날짜 변환 (YYYYMMDD 정수 형식 처리 및 문자열 처리)
    if '접수일' in df.columns:
        def parse_date(x):
            if isinstance(x, (pd.Timestamp, datetime)): return x
            try:
                s = str(x).replace(',', '').strip()
                # Remove common separators
                s = s.replace('.', '-').replace('/', '-')
                # Remove multiple spaces
                s = ' '.join(s.split())
                
                if len(s) == 8 and s.isdigit():
                    return pd.to_datetime(s, format='%Y%m%d', errors='coerce')
                return pd.to_datetime(s, errors='coerce')
            except:
                return pd.NaT
        df['접수일'] = df['접수일'].apply(parse_date)
    
    # 보험료 숫자 변환 (쉼표 제거 후 변환)
    if '보험료' in df.columns:
        df['보험료'] = df['보험료'].astype(str).str.replace(',', '', regex=False).str.strip()
        df['보험료'] = pd.to_numeric(df['보험료'], errors='coerce').fillna(0)
    
    # 회사명 표준화
    for col in ['회사', '원수사', '보험사', '제휴사']:
        if col in df.columns:
            df[col] = df[col].apply(standardize_name)
    
    return df


def load_rules_from_url(spreadsheet_url: str, sheet_name: str = "시상규칙") -> pd.DataFrame:
    """
    공개 스프레드시트에서 시상규칙 로드
    """
    df = load_public_sheet(spreadsheet_url, sheet_name)
    
    # 내장 함수로 정의하여 스코프 문제 방지
    def _standardize_name(name):
        if pd.isna(name): return name
        name = str(name).replace(' ', '').replace('_', '')
        if 'KB' in name: return 'KB손해보험'
        if '삼성' in name: return '삼성화재'
        if '메리츠' in name: return '메리츠화재'
        if '현대' in name: return '현대해상'
        if '한화' in name: return '한화손해보험'
        if '흥국' in name: return '흥국화재'
        if 'DB' in name: return 'DB손해보험'
        if '롯데' in name: return '롯데손해보험'
        return name

    # 회사명 표준화 (시상 규칙도 표준화 필요)
    for col in ['회사', '원수사', '보험사', '제휴사']:
        if col in df.columns:
            df[col] = df[col].apply(_standardize_name)
    
    column_mapping = {
        '제휴사': '회사',
        '보험사': '회사',
        '최종시상명': '시상명',
        '목표실적': '목표실적',
        '보상금액': '보상금액',
        '비교 시상': '비교시상',
        '비교시상': '비교시상',
        '포함상품': '포함상품',
        '상품 구분': '상품구분',
        '상품구분': '상품구분',
        '상품종류': '상품구분',
        '시작일': '시작일',
        '종료일': '종료일',
        '연속단계': '연속단계'
    }
    
    df = df.rename(columns=column_mapping)
    
    # 회사 컬럼이 없으면 시트명으로 대체
    if '회사' not in df.columns:
        df['회사'] = sheet_name
    
    # 목표실적, 보상금액, 단계별 목표/보상 숫자 변환
    numeric_cols = ['목표실적', '보상금액'] + [f'{i}단계목표' for i in range(1, 10)] + [f'{i}단계보상' for i in range(1, 10)]
    for col in numeric_cols:
        if col in df.columns:
            # 쉼표 제거 후 변환
            df[col] = df[col].astype(str).str.replace(',', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 지급률 숫자 변환
    if '지급률' in df.columns:
        # 문자열로 변환 후 % 및 쉼표 제거
        df['지급률'] = df['지급률'].astype(str).str.replace('%', '').str.replace(',', '')
        df['지급률'] = pd.to_numeric(df['지급률'], errors='coerce')
    
    # 시작일/종료일 날짜 변환
    # 시작일/종료일 날짜 변환 (강력한 파싱)
    def parse_rule_date(x):
        if pd.isna(x): return pd.NaT
        s = str(x).strip().replace('.', '-').replace('/', '-')
        return pd.to_datetime(s, errors='coerce')

    if '시작일' in df.columns:
        df['시작일'] = df['시작일'].apply(parse_rule_date)
    if '종료일' in df.columns:
        df['종료일'] = df['종료일'].apply(parse_rule_date)
    
    return df


def load_contracts_from_csv(uploaded_file) -> pd.DataFrame:
    """
    업로드된 CSV 파일에서 계약 데이터 로드
    
    Args:
        uploaded_file: Streamlit 업로드 파일
    
    Returns:
        pd.DataFrame: 계약 데이터
    """
    df = pd.read_csv(uploaded_file)
    
    if '접수일' in df.columns:
        df['접수일'] = pd.to_datetime(df['접수일'], errors='coerce')
    
    if '보험료' in df.columns:
        df['보험료'] = pd.to_numeric(df['보험료'], errors='coerce').fillna(0)
    
    return df


def load_rules_from_csv(uploaded_file) -> pd.DataFrame:
    """
    업로드된 CSV 파일에서 시상규칙 로드
    
    Args:
        uploaded_file: Streamlit 업로드 파일
    
    Returns:
        pd.DataFrame: 시상규칙 데이터
    """
    df = pd.read_csv(uploaded_file)
    
    # 회사명 표준화
    for col in ['회사', '원수사', '보험사', '제휴사']:
        if col in df.columns:
            df[col] = df[col].apply(standardize_name)
    
    for step in range(1, 10):
        target_col = f'{step}단계목표'
        reward_col = f'{step}단계보상'
        
        if target_col in df.columns:
            df[target_col] = pd.to_numeric(df[target_col], errors='coerce')
        if reward_col in df.columns:
            df[reward_col] = pd.to_numeric(df[reward_col], errors='coerce')
    
    if '지급률' in df.columns:
        # 문자열로 변환 후 % 및 쉼표 제거
        df['지급률'] = df['지급률'].astype(str).str.replace('%', '').str.replace(',', '')
        df['지급률'] = pd.to_numeric(df['지급률'], errors='coerce')
    
    # 시작일/종료일 날짜 변환
    if '시작일' in df.columns:
        df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
    if '종료일' in df.columns:
        df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
    
    return df


def validate_contracts(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    계약 데이터 유효성 검증
    """
    errors = []
    required_cols = ['접수일', '사원명', '모집인명', '계약자', '상품명', '상품종류', '보험료']
    
    missing = set(required_cols) - set(df.columns)
    if missing:
        errors.append(f"필수 컬럼 누락: {missing}")
    
    if errors:
        return False, errors
    
    # 경고만 표시 (에러 아님 - 데이터는 로드됨)
    warnings = []
    null_dates = df['접수일'].isna().sum()
    if null_dates > 0:
        warnings.append(f"참고: 접수일 NULL 값 {null_dates}건 (계산 시 제외)")
    
    negative_premium = (df['보험료'] < 0).sum()
    if negative_premium > 0:
        warnings.append(f"참고: 보험료 음수 값 {negative_premium}건 (계산 시 제외)")
    
    # 경고는 반환하지만 검증은 통과
    return True, warnings


def validate_rules(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    시상규칙 유효성 검증 (유연한 검증)
    """
    errors = []
    warnings = []
    required_cols = ['회사', '시상명', '유형']
    
    missing = set(required_cols) - set(df.columns)
    if missing:
        errors.append(f"필수 컬럼 누락: {missing}")
        return False, errors
    
    # 유형 검증 - 유효하지 않은 유형은 경고만 표시
    valid_types = ['정률형', '계단형', '연속형', '합산형']
    invalid_types = df[~df['유형'].isin(valid_types)]['유형'].unique().tolist()
    if invalid_types:
        # 경고만 표시하고 해당 행은 제외할 수 있도록
        warnings.append(f"참고: 일부 시상 유형은 처리되지 않습니다: {invalid_types}")
    
    # 정률형 지급률 검증 - 경고만 표시 (오류 아님)
    rate_rules = df[df['유형'] == '정률형']
    if not rate_rules.empty:
        if '지급률' not in df.columns:
            warnings.append("참고: 정률형 시상이 있으나 지급률 컬럼이 없습니다")
        else:
            missing_rate = rate_rules[rate_rules['지급률'].isna() | (rate_rules['지급률'] <= 0)]
            if not missing_rate.empty:
                warnings.append(f"참고: 지급률 미설정 정률형 시상 {len(missing_rate)}개 (계산 시 제외됨)")
    
    # 경고는 반환하되 검증은 통과
    return len(errors) == 0, errors + warnings


def classify_product(row: pd.Series) -> str:
    """
    상품 자동 분류 (최종 보완 버전)
    """
    # 0. 데이터 전처리
    상품명 = str(row.get('상품명', '')).replace(' ', '').strip()
    상품종류 = str(row.get('상품종류', '')).replace(' ', '').strip()
    계약종류 = str(row.get('계약종류', '')).replace(' ', '').strip()
    모집인명 = str(row.get('모집인명', '')).strip()
    계약자 = str(row.get('계약자가', row.get('계약자', ''))).strip()
    
    # 1. 본인계약 (최우선)
    if 모집인명 and 계약자 and 모집인명 == 계약자:
        return '본인계약'
        
    # 2. 펫보험 (키워드 우선)
    if '펫' in 상품명 or '펫' in 상품종류:
        return '펫보험'
    
    # 3. 실손보험 (키워드 우선)
    if '실손' in 상품명 or '실손' in 상품종류:
        return '실손보험'
        
    # 4. 자동차보험
    if '자동차' in 상품명 or '자동차' in 상품종류 or '자동차' in 계약종류:
        return '자동차보험'
    
    # 5. 단체보험
    if '단체' in 상품종류 or '단체' in 상품명:
        return '단체보험'
    
    # 6. 인보험 (보장성 우선)
    if '보장성' in 상품종류:
        return '인보험'
        
    # 7. 재물보험 (키워드 매칭 - 이미 실손/인보험 등은 걸러짐)
    if '재물성' in 상품종류 or any(kw in 상품명 for kw in ['재산', '배상']):
        return '재물보험'
    
    # 8. 화재 키워드 처리 (회사명 삼성화재 등 오판 방지를 위해 마지막에 배치)
    if '화재' in 상품명:
        # 이미 위에서 보장성이나 실손이 걸러졌다면, 남은 '화재' 키워드는 진짜 재물보험일 가능성이 높음
        return '재물보험'
        
    # 9. 인보험 보조 키워드
    if any(kw in 상품명 for kw in ['건강', '암', '상해', '질병', '종신', '생명']):
        return '인보험'
    
    return '기타'


def preprocess_contracts(df: pd.DataFrame, agent_name: Optional[str] = None) -> Tuple[pd.DataFrame, dict]:
    """
    계약 데이터 전처리 (디버깅 정보 포함)
    """
    stats = {
        'original_count': len(df),
        'self_contracts_removed': 0,
        'zero_premium_removed': 0,
        'agent_filtered': 0,
        'agent_count_before_filter': 0,
        'final_count': 0,
        'debug_info': {}
    }
    
    result = df.copy()
    
    # [접수일] 컬럼 표준화 (계약일자 -> 접수일)
    if '접수일' not in result.columns:
        for col in ['계약일자', '접수일자', '일자']:
            if col in result.columns:
                result['접수일'] = result[col]
                break
    
    # 날짜 형식 변환 (숫자형 20251127 등 대응)
    if '접수일' in result.columns:
        # 이미 datetime 타입이면 패스
        if not pd.api.types.is_datetime64_any_dtype(result['접수일']):
            def parse_date(x):
                if isinstance(x, (pd.Timestamp, datetime)): return x
                try:
                    s = str(x).replace(',', '').replace(' ', '').split('.')[0]
                    if len(s) == 8 and s.isdigit():
                        return pd.to_datetime(s, format='%Y%m%d', errors='coerce')
                    return pd.to_datetime(s, errors='coerce')
                except:
                    return pd.NaT
            result['접수일'] = result['접수일'].apply(parse_date)

    # [모집인명] 컬럼 표준화 (내부적으로 '모집인명' 통일)
    if '모집인명' not in result.columns:
        if '설계사' in result.columns:
            result['모집인명'] = result['설계사']
        elif '사원명' in result.columns:
            result['모집인명'] = result['사원명']
    
    # 내부 로직용 '설계사' 컬럼도 생성하되 '모집인명' 값을 따름
    result['설계사'] = result['모집인명']
    
    # 모집인명 표준화 (공백 제거)
    if '모집인명' in result.columns:
        result['모집인명'] = result['모집인명'].astype(str).str.strip()
        result['설계사'] = result['모집인명']
    if '사원명' in result.columns:
        result['사원명'] = result['사원명'].astype(str).str.strip()
    
    # [회사] 컬럼 생성
    if '회사' not in result.columns:
        # 우선순위대로 컬럼 선택
        for col in ['원수사', '보험사', '제휴사']:
            if col in result.columns:
                result['회사'] = result[col]
                break
        
        # 아직 '회사'가 없으면 상품명 기반 유추 (벡터화)
        if '회사' not in result.columns:
            result['회사'] = '기타보험사'
            prod_names = result['상품명'].fillna('').astype(str)
            
            # 주요 보험사 키워드 및 상품명 매핑 (벡터화)
            keywords = {
                'KB': 'KB손해보험', '삼성': '삼성화재', '메리츠': '메리츠화재', '현대': '현대해상', 
                'DB': 'DB손해보험', '한화': '한화손해보험', '흥국': '흥국화재', '롯데': '롯데손해보험'
            }
            for k, v in keywords.items():
                result.loc[prod_names.str.contains(k, na=False), '회사'] = v
    
    # 회사명 표준화 (벡터화)
    if '회사' in result.columns:
        result['회사'] = result['회사'].astype(str).str.replace(' ', '', regex=False).str.replace('_', '', regex=False)
        mapping = {
            'KB': 'KB손해보험', '삼성': '삼성화재', '메리츠': '메리츠화재', '현대': '현대해상',
            '한화': '한화손해보험', '흥국': '흥국화재', 'DB': 'DB손해보험', '롯데': '롯데손해보험'
        }
        for k, v in mapping.items():
            result.loc[result['회사'].str.contains(k, na=False), '회사'] = v

    # 디버깅: 날짜 범위 확인
    if '접수일' in result.columns:
        valid_dates = result['접수일'].dropna()
        if len(valid_dates) > 0:
            stats['debug_info']['date_range'] = f"{valid_dates.min()} ~ {valid_dates.max()}"
            stats['debug_info']['null_dates'] = int(result['접수일'].isna().sum())
    
    # 설계사 필터링 (모집인명 기준)
    if agent_name:
        before = len(result)
        # 디버깅: 해당 설계사 계약 수
        agent_contracts = result[result['모집인명'] == agent_name]
        stats['agent_count_before_filter'] = len(agent_contracts)
        result = agent_contracts
        stats['agent_filtered'] = before - len(result)
    
    # 계약상태 필터링 제거 (모든 계약 노출 요청)
    if '계약상태' in result.columns:
        # result = result[result['계약상태'] == '정상'] # 필터링 비활성화
        pass

    # 본인 계약 필터링 제거 (대신 카테고리로 분류됨)
    self_mask = pd.Series([False] * len(result), index=result.index)
    if '모집인명' in result.columns and '계약자' in result.columns:
        self_mask |= (result['모집인명'] == result['계약자'])
    
    stats['debug_info']['self_contract_count'] = int(self_mask.sum())
    # result = result[~self_mask] # 필터링 비활성화
    
    # 보험료 0 제외 (안전하게 숫자 변환 후 비교)
    before = len(result)
    if '보험료' in result.columns:
        # 콤마 제거 및 숫자 변환
        result['보험료'] = result['보험료'].astype(str).str.replace(',', '').str.strip()
        result['보험료'] = pd.to_numeric(result['보험료'], errors='coerce').fillna(0)
        
        stats['debug_info']['premium_dtype'] = str(result['보험료'].dtype)
        result = result[result['보험료'] != 0]
    stats['zero_premium_removed'] = before - len(result)
    
    # 상품 분류
    result['분류'] = result.apply(classify_product, axis=1)
    
    stats['final_count'] = len(result)
    
    return result, stats


def filter_by_products(contracts: pd.DataFrame, 포함상품: Optional[str], 상품구분: Optional[str] = None) -> pd.DataFrame:
    """
    포함상품 필터링
    - 포함상품이 있으면: 해당 상품명만 포함
    - 포함상품이 비어있고 상품구분이 있으면: 해당 상품분류에 속하는 모든 상품 포함
    """
    # 포함상품이 있으면 키워드 포함(contains)으로 필터링
    if not pd.isna(포함상품) and str(포함상품).strip() != '':
        keywords = [k.strip() for k in str(포함상품).split('|') if k.strip()]
        if keywords:
            # 여러 키워드 중 하나라도 포함된 경우를 찾기 위해 regex pattern 생성
            pattern = '|'.join(keywords)
            return contracts[contracts['상품명'].str.contains(pattern, na=False)]
    
    # 포함상품이 비어있고 상품구분이 있으면 해당 분류로 필터링
    if not pd.isna(상품구분) and str(상품구분).strip() != '':
        category = str(상품구분).strip()
        
        # 분류 컬럼이 있으면 직접 필터링
        if '분류' in contracts.columns:
            return contracts[contracts['분류'] == category]
        
        # 분류 컬럼이 없으면 상품명/상품종류로 매칭
        # 카테고리별 키워드 매핑
        category_keywords = {
            '인보험': ['인', '생명', '상해', '질병', '암', '건강'],
            '펫보험': ['펫', '애완', '반려'],
            '재물보험': ['재물', '화재', '재산', '건물'],
            '단체보험': ['단체'],
            '실손보험': ['실손'],
            '자동차보험': ['자동차'],
            '본인계약': []
        }
        
        keywords = category_keywords.get(category, [category])
        
        # 상품명이나 상품종류에 키워드가 포함된 경우 필터링
        mask = pd.Series([False] * len(contracts), index=contracts.index)
        for kw in keywords:
            if '상품명' in contracts.columns:
                mask |= contracts['상품명'].str.contains(kw, na=False)
            if '상품종류' in contracts.columns:
                mask |= contracts['상품종류'].str.contains(kw, na=False)
        
        return contracts[mask]
    
    # 둘 다 비어있으면 전체 반환
    return contracts


def filter_by_period(contracts: pd.DataFrame, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """
    기간 필터링
    """
    return contracts[
        (contracts['접수일'] >= pd.Timestamp(start_date)) & 
        (contracts['접수일'] <= pd.Timestamp(end_date))
    ]


def get_period_dates(period_type: str, base_date: datetime) -> Tuple[datetime, datetime]:
    """
    기간 유형에 따른 시작일/종료일 계산
    """
    if period_type == "월간":
        start_date = base_date.replace(day=1)
        if base_date.month == 12:
            end_date = base_date.replace(year=base_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = base_date.replace(month=base_date.month + 1, day=1) - timedelta(days=1)
    
    elif period_type == "주간":
        start_date = base_date - timedelta(days=base_date.weekday())
        end_date = start_date + timedelta(days=6)
    
    elif period_type == "분기":
        quarter_start_month = ((base_date.month - 1) // 3) * 3 + 1
        start_date = base_date.replace(month=quarter_start_month, day=1)
        quarter_end_month = quarter_start_month + 2
        if quarter_end_month > 12:
            end_date = base_date.replace(year=base_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = base_date.replace(month=quarter_end_month + 1, day=1) - timedelta(days=1)
    
    else:
        start_date = base_date.replace(day=1)
        if base_date.month == 12:
            end_date = base_date.replace(year=base_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = base_date.replace(month=base_date.month + 1, day=1) - timedelta(days=1)
    
    return start_date, end_date


def get_unique_agents(df: pd.DataFrame) -> List[str]:
    """
    계약 데이터에서 고유한 사원명 목록 추출
    """
    if '사원명' not in df.columns:
        return []
    return sorted(df['사원명'].dropna().unique().tolist())


def get_unique_companies(df: pd.DataFrame) -> List[str]:
    """
    시상규칙에서 고유한 회사명 목록 추출
    """
    if '회사' not in df.columns:
        return []
    return sorted(df['회사'].dropna().unique().tolist())


def load_consecutive_rules(file_path: str = None) -> pd.DataFrame:
    """
    연속형 시상 규칙 로드
    
    Args:
        file_path: CSV 파일 경로 (None이면 기본 경로 사용)
    
    Returns:
        pd.DataFrame: 연속형 시상 규칙 데이터
    """
    import os
    
    if file_path is None:
        # 기본 경로
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_dir, 'sample_data', '연속형시상규칙.csv')
    
    if not os.path.exists(file_path):
        # 파일이 없으면 빈 DataFrame 반환
        return pd.DataFrame(columns=['회사', '시상명', '구간번호', '시작일', '종료일', '목표실적', '이전구간조건', '보상금액'])
    
    df = pd.read_csv(file_path)
    
    # 컬럼명 매핑
    mapping = {
        '제휴사': '회사',
        '보험사': '회사',
        '최종시상명': '시상명',
        '연속단계': '구간번호'
    }
    df = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
    
    # 회사명 표준화
    for col in ['회사', '원수사', '보험사', '제휴사']:
        if col in df.columns:
            df[col] = df[col].apply(standardize_name)
    
    # 숫자 컬럼 변환
    numeric_cols = ['구간번호', '목표실적', '이전구간조건', '보상금액']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(',', '', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 날짜 컬럼 변환
    if '시작일' in df.columns:
        df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
    if '종료일' in df.columns:
        df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
    
    return df


def get_consecutive_award_structure(consecutive_rules: pd.DataFrame, award_name: str, company: str) -> dict:
    """
    특정 연속형 시상의 구조 분석
    
    Args:
        consecutive_rules: 연속형 시상 규칙 DataFrame
        award_name: 시상명
        company: 회사명
    
    Returns:
        dict: 구간별 구조화된 정보
    """
    # 해당 시상 필터링 (회사명 유연하게 매칭: KB손보 vs KB손해보험 등)
    def company_match(c1, c2):
        if pd.isna(c1) or pd.isna(c2): return False
        c1, c2 = str(c1).replace(' ', ''), str(c2).replace(' ', '')
        return c1 in c2 or c2 in c1

    award_rules = consecutive_rules[
        (consecutive_rules['시상명'] == award_name) & 
        (consecutive_rules['회사'].apply(lambda x: company_match(x, company)))
    ].copy()
    
    if award_rules.empty:
        return {}
    
    # 구간별 그룹화
    structure = {
        'award_name': award_name,
        'company': company,
        'total_periods': int(award_rules['구간번호'].max()),
        'periods': {}
    }
    
    for period_num in sorted(award_rules['구간번호'].unique()):
        period_data = award_rules[award_rules['구간번호'] == period_num]
        
        period_info = {
            'period_num': int(period_num),
            'start_date': period_data['시작일'].min(),
            'end_date': period_data['종료일'].max(),
            'targets': []
        }
        
        # 목표별 정보 정렬
        for _, row in period_data.sort_values('목표실적').iterrows():
            target_info = {
                'target': row['목표실적'],
                'prev_condition': row['이전구간조건'] if pd.notna(row['이전구간조건']) and row['이전구간조건'] > 0 else None,
                'reward': row['보상금액']
            }
            period_info['targets'].append(target_info)
        
        structure['periods'][int(period_num)] = period_info
    
    return structure
