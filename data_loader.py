import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
import re
import urllib.parse
import ssl
import urllib.request
import io

def extract_sheet_id(url: str) -> Optional[str]:
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    return match.group(1) if match else None

def get_public_sheet_csv_url(spreadsheet_url: str, sheet_name: str) -> str:
    sheet_id = extract_sheet_id(spreadsheet_url)
    if not sheet_id: raise ValueError("Invalid URL")
    encoded_name = urllib.parse.quote(sheet_name)
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={encoded_name}"

def load_public_sheet(url: str, name: str) -> pd.DataFrame:
    csv_url = get_public_sheet_csv_url(url, name)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(csv_url, context=ssl_context) as response:
        data = response.read().decode('utf-8')
    return pd.read_csv(io.StringIO(data))

def standardize_name(name):
    if pd.isna(name): return name
    name = str(name).replace(' ', '').replace('_', '')
    for k in ['KB', '삼성', '메리츠', '현대', '한화', '흥국', 'DB', '롯데']:
        if k in name: return f"{k}손해보험" if k != '삼성' and k != '현대' else f"{k}화재"
    return name

def load_contracts_from_url(url: str) -> pd.DataFrame:
    df = load_public_sheet(url, "계약데이터")
    df = df.rename(columns={'계약일자': '접수일'})
    def parse_date(x):
        try:
            s = str(x).strip()
            if len(s) == 8 and s.isdigit(): return pd.to_datetime(s, format='%Y%m%d')
            return pd.to_datetime(s)
        except: return pd.NaT
    df['접수일'] = df['접수일'].apply(parse_date)
    df['보험료'] = pd.to_numeric(df['보험료'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    return df

def load_rules_from_url(url: str) -> pd.DataFrame:
    df = load_public_sheet(url, "시상규칙")
    df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
    df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
    for i in range(1, 10):
        for col in [f'{i}단계목표', f'{i}단계보상']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    return df

def load_contracts_from_csv(file) -> pd.DataFrame:
    df = pd.read_csv(file)
    df['접수일'] = pd.to_datetime(df['접수일'], errors='coerce')
    df['보험료'] = pd.to_numeric(df['보험료'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    return df

def load_rules_from_csv(file) -> pd.DataFrame:
    df = pd.read_csv(file)
    df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
    df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
    return df

def classify_product(row) -> str:
    name = str(row.get('상품명', '')).replace(' ', '')
    kind = str(row.get('상품종류', '')).replace(' ', '')
    if row.get('모집인명') == row.get('계약자'): return '본인계약'
    if '펫' in name: return '펫보험'
    if '실손' in name: return '실손보험'
    if '자동차' in name: return '자동차보험'
    if '단체' in kind: return '단체보험'
    if '보장' in kind: return '인보험'
    if '재물' in kind or '화재' in name: return '재물보험'
    return '기타'

def preprocess_contracts(df, agent_name=None):
    res = df.copy()
    if '모집인명' not in res.columns: res['모집인명'] = res.get('사원명', 'Unknown')
    if agent_name: res = res[res['모집인명'] == agent_name]
    res['분류'] = res.apply(classify_product, axis=1)
    return res, {}

def get_period_dates(ptype, base):
    start = base.replace(day=1)
    if base.month == 12: end = base.replace(year=base.year+1, month=1, day=1) - timedelta(days=1)
    else: end = base.replace(month=base.month+1, day=1) - timedelta(days=1)
    return start, end

def load_consecutive_rules():
    return pd.DataFrame() # Simplified for final
