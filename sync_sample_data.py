"""
연속형 시상 로컬 데이터 동기화 스크립트
Google 스프레드시트에서 최신 데이터를 가져와 sample_data 폴더에 저장합니다.
"""

import pandas as pd
import os
from data_loader import load_contracts_from_url, load_rules_from_url, load_consecutive_rules

def sync_data():
    spreadsheet_url = "https://docs.google.com/spreadsheets/d/1W0eVca5rbpjXoiw65DaVkIY8793KRkoMH8oi8BHp-ow/edit"
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sample_dir = os.path.join(base_dir, 'sample_data')
    
    if not os.path.exists(sample_dir):
        os.makedirs(sample_dir)
        
    print(f"🚀 동기화 시작: {spreadsheet_url}")
    
    try:
        # 1. 계약 데이터 동기화
        print("📥 계약 데이터 로드 중...")
        contracts_df = load_contracts_from_url(spreadsheet_url, "RAW_계약")
        contracts_path = os.path.join(sample_dir, '계약데이터.csv')
        contracts_df.to_csv(contracts_path, index=False)
        print(f"✅ 계약 데이터 저장 완료: {len(contracts_df)}건")
        
        # 2. 시상 규칙 동기화 (KB, 삼성 합본)
        print("📥 시상 규칙 로드 중...")
        rules_sheets = ["KB", "삼성"]
        rules_dfs = []
        for sheet in rules_sheets:
            try:
                df = load_rules_from_url(spreadsheet_url, sheet)
                if '회사' not in df.columns:
                    df['회사'] = sheet
                rules_dfs.append(df)
                print(f"  - {sheet} 시트 로드 완료: {len(df)}개")
            except Exception as e:
                print(f"  ⚠️ {sheet} 시트 로드 실패: {e}")
        
        if rules_dfs:
            combined_rules = pd.concat(rules_dfs, ignore_index=True)
            rules_path = os.path.join(sample_dir, '시상규칙.csv')
            combined_rules.to_csv(rules_path, index=False)
            print(f"✅ 시상 규칙 저장 완료: {len(combined_rules)}개")
            
        # 3. 연속형 시상 규칙 동기화
        print("📥 연속형 시상 규칙 로드 중...")
        # '삼성' 시트에 연속형 규칙이 포함되어 있음
        try:
             from data_loader import load_public_sheet
             con_df = load_public_sheet(spreadsheet_url, "삼성")
             
             # 연속형 필터링 (유형 == '연속형')
             if '유형' in con_df.columns:
                 con_df = con_df[con_df['유형'] == '연속형'].copy()
             
             # 컬럼명 변환
             mapping = {
                 '제휴사': '회사',
                 '보험사': '회사',
                 '최종시상명': '시상명'
             }
             con_df = con_df.rename(columns={k: v for k, v in mapping.items() if k in con_df.columns})
             
             # 숫자 컬럼 변환
             numeric_cols = ['구간번호', '목표실적', '이전구간조건', '보상금액']
             for col in numeric_cols:
                 if col in con_df.columns:
                     con_df[col] = con_df[col].astype(str).str.replace(',', '', regex=False)
                     con_df[col] = pd.to_numeric(con_df[col], errors='coerce').fillna(0)
             
             if '시작일' in con_df.columns:
                 con_df['시작일'] = pd.to_datetime(con_df['시작일'], errors='coerce')
             if '종료일' in con_df.columns:
                 con_df['종료일'] = pd.to_datetime(con_df['종료일'], errors='coerce')
                 
             con_path = os.path.join(sample_dir, '연속형시상규칙.csv')
             con_df.to_csv(con_path, index=False)
             print(f"✅ 연속형 시상 규칙 저장 완료: {len(con_df)}개")
        except Exception as e:
             print(f"  ⚠️ 연속형 시상 규칙 로드 실패: {e}")

        print("\n✨ 모든 데이터가 최신 상태로 동기화되었습니다.")
        
    except Exception as e:
        print(f"\n❌ 동기화 도중 오류 발생: {e}")

if __name__ == "__main__":
    sync_data()
