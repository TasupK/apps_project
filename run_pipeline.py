import argparse
import glob
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

from agents.monitor_agent import run_monitor
from graph.state import make_initial_state
from graph.workflow import build_graph


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"


def load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def run_command(command: list[str]) -> None:
    print(f"Executing: {' '.join(command)}")
    result = subprocess.run(command, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(command)}")


def phase2_command(event_file: Path, output_file: Path, args: argparse.Namespace) -> list[str]:
    provider = args.search_provider or os.environ.get("PHASE2_SEARCH_PROVIDER") or "llm_plan"
    query_mode = args.query_mode
    extraction_mode = args.extraction_mode

    if provider == "serpapi" and not os.environ.get("SERPAPI_API_KEY"):
        print("SERPAPI_API_KEY is missing; falling back to llm_plan so the pipeline can run offline.")
        provider = "llm_plan"
        query_mode = "deterministic"
        extraction_mode = "none"

    return [
        sys.executable,
        "-m",
        "agents.web_research.agent",
        "--input",
        str(event_file),
        "--search-mode",
        "live",
        "--search-provider",
        provider,
        "--query-mode",
        query_mode,
        "--extraction-mode",
        extraction_mode,
        "--max-candidates",
        str(args.max_candidates),
        "--output",
        str(output_file),
    ]


def run_phase3(candidate_results_file: Path, output_file: Path, mode: str) -> None:
    command = [
        sys.executable,
        "-m",
        "agents.evaluation_agent",
        "--candidate-results",
        str(candidate_results_file),
        "--mode",
        mode,
        "--output",
        str(output_file),
    ]
    run_command(command)


def run_phase4(shortage_event_file: Path, evaluation_report_file: Path, auto_approve: bool) -> dict:
    shortage_event = json.loads(shortage_event_file.read_text(encoding="utf-8"))
    evaluation_report = json.loads(evaluation_report_file.read_text(encoding="utf-8"))

    graph = build_graph()
    material_id = shortage_event.get("material_id", "unknown")
    state = make_initial_state(f"wf-{material_id}-{uuid.uuid4().hex[:6]}")
    state["shortage_event"] = {
        "material_id": shortage_event.get("material_id"),
        "description": shortage_event.get("material_name"),
        "shortage_qty": shortage_event.get("shortage_qty", 0),
    }
    state["evaluation_report_batch"] = evaluation_report

    config = {"configurable": {"thread_id": state["workflow_id"]}}
    for _ in graph.stream(state, config=config):
        pass

    current_state = graph.get_state(config).values
    print(f"Phase 4 status: {current_state['status']}")

    if current_state["status"] == "APPROVAL_PENDING" and auto_approve:
        current_state["approval"] = {
            "required": True,
            "approved": True,
            "approver": "run_pipeline",
            "approved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        graph.update_state(config, current_state)
        for _ in graph.stream(None, config=config):
            pass
        current_state = graph.get_state(config).values
        print(f"Phase 4 status after auto approval: {current_state['status']}")

    return current_state


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run BuyBee Phase 1-4 pipeline.")
    parser.add_argument("--auto-approve", action="store_true", help="Automatically approve Phase 4 approval-pending items.")
    parser.add_argument("--search-provider", choices=["llm_plan", "serpapi"], help="Phase 2 search provider.")
    parser.add_argument("--query-mode", choices=["deterministic", "llm"], default="deterministic")
    parser.add_argument("--extraction-mode", choices=["none", "llm"], default="none")
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--mode", choices=["normal", "urgent"], default="urgent", help="Phase 3 scoring mode.")
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    args = build_argument_parser().parse_args()
    load_dotenv()
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("=== [Phase 1] Running Monitor Agent ===")
    run_monitor()

    event_files = sorted(Path(path) for path in glob.glob(str(OUTPUT_DIR / "shortage_event_*.json")))
    if not event_files:
        print("No shortage events detected. Exiting pipeline.")
        return

    final_states = []
    for event_file in event_files:
        mat_id = event_file.stem.replace("shortage_event_", "")
        candidate_file = OUTPUT_DIR / f"candidate_results_{mat_id}.json"
        evaluation_file = OUTPUT_DIR / f"evaluation_report_batch_{mat_id}.json"

        print(f"\n=== [Phase 2] Web Research for {mat_id} ===")
        run_command(phase2_command(event_file, candidate_file, args))

        print(f"\n=== [Phase 3] Evaluation for {mat_id} ===")
        run_phase3(candidate_file, evaluation_file, args.mode)

        print(f"\n=== [Phase 4] HITL Workflow for {mat_id} ===")
        final_states.append(run_phase4(event_file, evaluation_file, args.auto_approve))

    print("\n=== Pipeline Execution Completed ===")
    for state in final_states:
        print(f"- {state['workflow_id']}: {state['status']}")


if __name__ == "__main__":
    main()
