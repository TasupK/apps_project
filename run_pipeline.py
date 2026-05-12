import os
import glob
import subprocess
from agents.monitor_agent import run_monitor

# 여기에 발급받으신 실제 키를 직접 입력하세요. (GitHub에 올릴 때는 꼭 가리세요!)
os.environ["OPENAI_API_KEY"] = "http://chatgpt.com/#settings/DataControls"
os.environ["SERPAPI_API_KEY"] = "https://serpapi.com/searches/reports"

def main():
    print("=== [Phase 1] Running Monitor Agent ===")
    # Phase 1: 재고 감지 및 이벤트 생성
    run_monitor()
    
    # output/ 폴더에서 생성된 이벤트 파일 찾기
    event_files = glob.glob("output/shortage_event_*.json")
    if not event_files:
        print("No shortage events detected. Exiting pipeline.")
        return
        
    print(f"\n=== [Phase 2] Running Web Research Agent for {len(event_files)} events ===")
    
    # Phase 2: 각 이벤트 파일별로 웹 검색 에이전트 실행
    for event_file in event_files:
        print(f"\n-> Processing event: {event_file}")
        
        # 파일명에서 material_id 추출 (예: shortage_event_MAT-BRG-001.json -> MAT-BRG-001)
        basename = os.path.basename(event_file)
        mat_id = basename.replace("shortage_event_", "").replace(".json", "")
        output_file = os.path.join("output", f"candidate_results_{mat_id}.json")
        
        # Phase 2 명령어 구성
        cmd = [
            "python", "-m", "agents.web_research.agent",
            "--input", event_file,
            "--search-mode", "live",
            "--search-provider", "serpapi",
            "--query-mode", "llm",
            "--extraction-mode", "llm",
            "--max-candidates", "5",
            "--output", output_file
        ]
        
        print(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print(f"Successfully generated: {output_file}")
        else:
            print(f"Error occurred while processing: {event_file}")
            
    print("\n=== Pipeline Execution Completed ===")

if __name__ == "__main__":
    main()
