import pandas as pd
import time
from datetime import datetime
from incentive_engine import calculate_all_agents_awards
from data_loader import load_consecutive_rules

def benchmark():
    print("🚀 벤치마크 시작...")
    
    # 데이터 로드
    contracts = pd.read_csv('sample_data/계약데이터.csv')
    rules = pd.read_csv('sample_data/시상규칙.csv')
    consecutive_rules = load_consecutive_rules()
    
    # 날짜 형식 변환
    contracts['접수일'] = pd.to_datetime(contracts['접수일'])
    rules['시작일'] = pd.to_datetime(rules['시작일'])
    rules['종료일'] = pd.to_datetime(rules['종료일'])
    
    from data_loader import preprocess_contracts
    
    start_time = time.time()
    
    # 전처리 시간 측정
    all_processed_df, all_stats = preprocess_contracts(contracts, agent_name=None)
    mid_time = time.time()
    
    # 계산 시간 측정
    results = calculate_all_agents_awards(
        all_processed_df,
        rules,
        datetime(2025, 10, 1),
        datetime(2025, 11, 30),
        consecutive_rules=consecutive_rules
    )
    
    end_time = time.time()
    
    print(f"✅ 전처리 완료! ({mid_time - start_time:.2f}초)")
    print(f"✅ 계산 완료! 결과 건수: {len(results)}건 ({end_time - mid_time:.2f}초)")
    print(f"⏱️ 총 소요 시간: {end_time - start_time:.2f}초")

if __name__ == "__main__":
    benchmark()
