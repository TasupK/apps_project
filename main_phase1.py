import os
import sys
import json
from db.seed_data import seed
from agents.monitor_agent import run_monitor

def main():
    print("=== BuyBee Phase 1: Integrated Execution ===")
    
    # 1. DB 초기화 및 데이터 시딩
    print("\n[Step 1] Initializing Database & Seeding Mock Data...")
    try:
        # 기존 DB 삭제 후 새로 생성 (스키마 반영)
        if os.path.exists("buybee.db"):
            os.remove("buybee.db")
        seed()
    except Exception as e:
        print(f"Error during seeding: {e}")
        sys.exit(1)

    # 2. 모니터 에이전트 실행
    print("\n[Step 2] Running Monitor Agent...")
    try:
        run_monitor()
    except Exception as e:
        print(f"Error during monitoring: {e}")
        sys.exit(1)

    print("\n=== Phase 1 Execution Completed Successfully ===")

if __name__ == "__main__":
    main()
