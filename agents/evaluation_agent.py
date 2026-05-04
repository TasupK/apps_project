"""Phase 3 evaluation engine for generic fasteners."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import argparse
import csv
import json
from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.reporting_agent import write_evaluation_report
from tools.spec_normalizer import FastenerSpec, parse_fastener_spec


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FASTENER_SHORTAGE_EVENT = PROJECT_ROOT / ".planning" / "phase-3" / "fastener_shortage_event.sample.json"
DEFAULT_MATERIAL_MASTER = PROJECT_ROOT / "material_master.csv"
DEFAULT_VENDOR_SOURCING = PROJECT_ROOT / "vendor_sourcing.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "evaluation_report.json"
DEFAULT_BATCH_OUTPUT = PROJECT_ROOT / "output" / "evaluation_report_batch.json"


MATERIAL_GROUPS = {
    "SUS304": ("stainless", 1),
    "SUS316": ("stainless", 2),
    "4.8": ("carbon_steel_strength", 1),
    "8.8": ("carbon_steel_strength", 2),
    "10.9": ("carbon_steel_strength", 3),
    "STEEL": ("unknown", 0),
}

SOURCE_TYPE_BREAKDOWN = {
    "official_distributor": {"official_distributor": True, "datasheet_bonus": 30},
    "manufacturer_page": {"official_distributor": False, "datasheet_bonus": 25},
    "industrial_marketplace": {"official_distributor": False, "datasheet_bonus": 18},
    "marketplace": {"official_distributor": False, "datasheet_bonus": 10},
    "unknown": {"official_distributor": False, "datasheet_bonus": 0},
}

WEIGHTS = {
    "normal": {
        "compatibility_score": 50,
        "lead_time_score": 20,
        "price_score": 15,
        "moq_score": 10,
        "source_trust_score": 5,
    },
    "urgent": {
        "compatibility_score": 50,
        "lead_time_score": 30,
        "price_score": 10,
        "moq_score": 5,
        "source_trust_score": 5,
    },
}


def _snake_source_type(raw: str) -> str:
    return raw.strip().lower().replace(" ", "_")


def _bool(raw: str | bool | None) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().upper() == "TRUE"


def _material_decision(original: str | None, candidate: str | None) -> tuple[str, str, str]:
    if not original or not candidate:
        return "review_required", "High", "Material information is incomplete."

    if original == candidate:
        return "recommend", "Low", "Material is identical."

    original_group, original_rank = MATERIAL_GROUPS.get(original, ("unknown", 0))
    candidate_group, candidate_rank = MATERIAL_GROUPS.get(candidate, ("unknown", 0))

    if original_group != candidate_group:
        return "reject", "High", "Material group mismatch."

    if candidate_rank > original_rank:
        return "conditional_approve", "Medium", "Material is upgraded and may affect cost."

    if original_group == "carbon_steel_strength" and candidate_rank < original_rank:
        return "reject", "High", "Strength grade is downgraded."

    return "review_required", "Medium", "Material is downgraded and needs buyer review."


def _critical_spec_check(original: FastenerSpec, candidate: FastenerSpec) -> dict:
    diameter_match = original.diameter == candidate.diameter
    pitch_match = original.pitch == candidate.pitch
    thread_system_match = original.thread_system == candidate.thread_system
    length_match = original.length_mm == candidate.length_mm
    critical_mismatch = not all([diameter_match, pitch_match, thread_system_match, length_match])

    return {
        "diameter_match": diameter_match,
        "pitch_match": pitch_match,
        "thread_system_match": thread_system_match,
        "length_match": length_match,
        "critical_mismatch": critical_mismatch,
    }


def _highlight_differences(original: FastenerSpec, candidate: FastenerSpec) -> list[dict]:
    differences = []
    for field_name, impact in {
        "diameter": "Diameter mismatch prevents interchangeability.",
        "pitch": "Thread pitch mismatch prevents proper fastening.",
        "thread_system": "Thread system mismatch prevents compatibility.",
        "length_mm": "Length mismatch creates assembly risk.",
        "material": "Material difference may affect corrosion, strength, or cost.",
    }.items():
        original_value = getattr(original, field_name)
        candidate_value = getattr(candidate, field_name)
        if original_value != candidate_value:
            differences.append(
                {
                    "spec": field_name,
                    "original": original_value,
                    "candidate": candidate_value,
                    "impact": impact,
                }
            )
    return differences


def _source_trust_breakdown(candidate: dict) -> tuple[dict, int]:
    source_type = _snake_source_type(candidate.get("source_type") or candidate.get("SOURCE_TYPE", "unknown"))
    source_meta = SOURCE_TYPE_BREAKDOWN.get(source_type, SOURCE_TYPE_BREAKDOWN["unknown"])
    breakdown = {
        "official_distributor": source_meta["official_distributor"],
        "datasheet_available": len(candidate.get("SPEC_EVIDENCE", "")) > 20,
        "stock_visible": _bool(candidate.get("STOCK_LISTED")),
        "price_visible": _bool(candidate.get("PRICE_LISTED")),
        "leadtime_visible": _bool(candidate.get("LEADTIME_LISTED")),
    }
    score = source_meta["datasheet_bonus"]
    score += 20 if breakdown["stock_visible"] else 0
    score += 20 if breakdown["price_visible"] else 0
    score += 20 if breakdown["leadtime_visible"] else 0
    score += 10 if candidate.get("SOURCE_URL") else 0
    return breakdown, min(score, 100)


def _lead_time_score(days: int) -> int:
    if days <= 1:
        return 100
    if days <= 3:
        return 85
    if days <= 7:
        return 65
    if days <= 14:
        return 45
    return 20


def _price_score(price: int, min_price: int) -> int:
    if price <= 0:
        return 0
    return round((min_price / price) * 100)


def _moq_score(moq: int | None) -> int:
    if moq is None:
        return 70
    if moq <= 10:
        return 100
    if moq <= 30:
        return 80
    if moq <= 50:
        return 60
    return 40


def _weighted_total(scores: dict, mode: str) -> int:
    weights = WEIGHTS[mode]
    total = sum(scores[key] * weights[key] for key in weights)
    return round(total / sum(weights.values()))


def _compatibility_score(critical_check: dict, material_decision: str) -> int:
    if critical_check["critical_mismatch"]:
        return 0
    if material_decision == "recommend":
        return 100
    if material_decision == "conditional_approve":
        return 88
    if material_decision == "review_required":
        return 72
    return 20


def _decision_context(
    critical_check: dict,
    material_decision: tuple[str, str, str],
    source_trust_score: int,
    differences: list[dict],
) -> dict:
    decision, risk_level, reason_seed = material_decision
    if critical_check["critical_mismatch"]:
        return {
            "decision": "reject",
            "risk_level": "High",
            "recommendation_reason": "Not recommended for substitution.",
            "approval_conditions": [],
            "rejection_reason": "Critical spec mismatch.",
            "review_required": False,
        }

    if source_trust_score < 50 and decision != "reject":
        return {
            "decision": "review_required",
            "risk_level": "High",
            "recommendation_reason": "Specs are close, but source trust is too low for automatic recommendation.",
            "approval_conditions": [],
            "rejection_reason": None,
            "review_required": True,
        }

    approval_conditions = []
    if decision == "conditional_approve" and any(item["spec"] == "material" for item in differences):
        approval_conditions.append("Confirm material substitution impact on cost and corrosion requirements.")

    return {
        "decision": decision,
        "risk_level": risk_level,
        "recommendation_reason": reason_seed,
        "approval_conditions": approval_conditions,
        "rejection_reason": None,
        "review_required": decision == "review_required",
    }


def evaluate_fastener_candidate(
    target_material: dict,
    candidate_material: dict,
    mode: str = "normal",
) -> dict:
    target_spec = parse_fastener_spec(target_material["spec_text"])
    candidate_spec = parse_fastener_spec(candidate_material["spec_text"])

    critical_check = _critical_spec_check(target_spec, candidate_spec)
    material_decision = _material_decision(target_spec.material, candidate_spec.material)
    differences = _highlight_differences(target_spec, candidate_spec)
    trust_breakdown, source_trust_score = _source_trust_breakdown(candidate_material)

    scores = {
        "compatibility_score": _compatibility_score(critical_check, material_decision[0]),
        "source_trust_score": source_trust_score,
        "lead_time_score": _lead_time_score(int(candidate_material["lead_time_days"])),
        "price_score": _price_score(int(candidate_material["price_krw"]), int(candidate_material["min_price_krw"])),
        "moq_score": _moq_score(candidate_material.get("moq")),
    }
    scores["final_score"] = _weighted_total(scores, mode)

    decision_context = _decision_context(critical_check, material_decision, source_trust_score, differences)

    return {
        "report_id": f"ER-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": mode,
        "target_material": {
            "material_id": target_material["material_id"],
            "description": target_material["description"],
            "spec": asdict(target_spec),
        },
        "candidate_material": {
            "candidate_id": candidate_material["candidate_id"],
            "vendor_name": candidate_material["vendor_name"],
            "source_url": candidate_material["source_url"],
            "source_type": _snake_source_type(candidate_material["source_type"]),
            "price_krw": int(candidate_material["price_krw"]),
            "lead_time_days": int(candidate_material["lead_time_days"]),
            "moq": candidate_material.get("moq"),
            "spec": asdict(candidate_spec),
        },
        "spec_analysis": {
            "critical_spec_check": critical_check,
            "highlighted_differences": differences,
        },
        "scores": scores,
        "source_trust_breakdown": trust_breakdown,
        "decision_context": decision_context,
    }


def load_sample_phase3_inputs() -> tuple[dict, dict]:
    target_material = {
        "material_id": "BT-H-M10-50",
        "description": "Hex bolt",
        "spec_text": "Hex head bolt M10 thread pitch 1.5 length 50mm. Stainless steel 304.",
    }
    candidate_material = {
        "candidate_id": "CAND-001",
        "vendor_name": "MISUMI Korea",
        "source_url": "https://example.com/item/123",
        "source_type": "official_distributor",
        "price_krw": 450,
        "min_price_krw": 450,
        "lead_time_days": 1,
        "moq": 10,
        "spec_text": "Hex head bolt M10 thread pitch 1.5 length 50mm. Stainless steel 316.",
        "SPEC_EVIDENCE": "Datasheet available with metric dimensions and material grade.",
        "PRICE_LISTED": True,
        "STOCK_LISTED": True,
        "LEADTIME_LISTED": True,
    }
    return target_material, candidate_material


def _read_csv_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _load_fastener_csv_context(
    shortage_event_path: Path = DEFAULT_FASTENER_SHORTAGE_EVENT,
    material_master_path: Path = DEFAULT_MATERIAL_MASTER,
    vendor_sourcing_path: Path = DEFAULT_VENDOR_SOURCING,
) -> tuple[dict, dict[str, dict], list[dict]]:
    shortage_event = json.loads(shortage_event_path.read_text(encoding="utf-8"))
    material_rows = _read_csv_rows(material_master_path)
    vendor_rows = _read_csv_rows(vendor_sourcing_path)
    material_by_id = {row["MATERIAL_ID"]: row for row in material_rows}
    fastener_candidates = [
        row for row in vendor_rows
        if row["MATERIAL_ID"] in material_by_id
        and material_by_id[row["MATERIAL_ID"]]["CATEGORY"] == "Fastener"
    ]
    if not fastener_candidates:
        raise ValueError("No fastener candidates found in vendor_sourcing.csv")
    return shortage_event, material_by_id, fastener_candidates


def _target_from_context(shortage_event: dict, material_by_id: dict[str, dict]) -> dict:
    original_row = material_by_id[shortage_event["material_id"]]
    return {
        "material_id": shortage_event["material_id"],
        "description": original_row["MATERIAL_ID"],
        "spec_text": original_row["TECHNICAL_SPECIFICATION"],
    }


def _candidate_from_context(
    candidate_row: dict,
    material_by_id: dict[str, dict],
    min_price: int,
) -> dict:
    candidate_material_row = material_by_id[candidate_row["MATERIAL_ID"]]
    return {
        "candidate_id": candidate_row["CANDIDATE_ID"],
        "vendor_name": candidate_row["VENDOR_NAME"],
        "source_url": candidate_row["SOURCE_URL"],
        "source_type": candidate_row["SOURCE_TYPE"],
        "price_krw": int(candidate_row["UNIT_PRICE_KRW"]),
        "min_price_krw": min_price,
        "lead_time_days": int(candidate_row["LEAD_TIME_DAYS"]),
        "moq": None,
        "spec_text": candidate_material_row["TECHNICAL_SPECIFICATION"],
        "SPEC_EVIDENCE": candidate_row["SPEC_EVIDENCE"],
        "PRICE_LISTED": candidate_row["PRICE_LISTED"],
        "STOCK_LISTED": candidate_row["STOCK_LISTED"],
        "LEADTIME_LISTED": candidate_row["LEADTIME_LISTED"],
    }


def load_fastener_inputs_from_csv(
    shortage_event_path: Path = DEFAULT_FASTENER_SHORTAGE_EVENT,
    material_master_path: Path = DEFAULT_MATERIAL_MASTER,
    vendor_sourcing_path: Path = DEFAULT_VENDOR_SOURCING,
) -> tuple[dict, dict]:
    shortage_event, material_by_id, fastener_candidates = _load_fastener_csv_context(
        shortage_event_path,
        material_master_path,
        vendor_sourcing_path,
    )
    min_price = min(int(row["UNIT_PRICE_KRW"]) for row in fastener_candidates)
    chosen = fastener_candidates[0]
    return _target_from_context(shortage_event, material_by_id), _candidate_from_context(chosen, material_by_id, min_price)


def _decision_priority(decision: str) -> int:
    return {
        "recommend": 0,
        "conditional_approve": 1,
        "review_required": 2,
        "reject": 3,
    }.get(decision, 4)


def _next_action(results: list[dict]) -> str:
    viable = [
        report for report in results
        if report["decision_context"]["decision"] in {"recommend", "conditional_approve"}
    ]
    if viable:
        return "approval_pending"
    if any(report["decision_context"]["decision"] == "review_required" for report in results):
        return "manual_review"
    return "no_viable_candidate"


def build_batch_report(reports: list[dict], mode: str) -> dict:
    sorted_reports = sorted(
        reports,
        key=lambda report: (
            _decision_priority(report["decision_context"]["decision"]),
            -report["scores"]["final_score"],
        ),
    )
    decision_counts: dict[str, int] = {}
    for report in sorted_reports:
        decision = report["decision_context"]["decision"]
        decision_counts[decision] = decision_counts.get(decision, 0) + 1

    return {
        "batch_report_id": f"BER-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": mode,
        "candidate_count": len(sorted_reports),
        "decision_counts": decision_counts,
        "top_candidate_id": sorted_reports[0]["candidate_material"]["candidate_id"] if sorted_reports else None,
        "next_action": _next_action(sorted_reports),
        "items": sorted_reports,
    }


def evaluate_fastener_candidates_from_csv(
    mode: str = "urgent",
    shortage_event_path: Path = DEFAULT_FASTENER_SHORTAGE_EVENT,
    material_master_path: Path = DEFAULT_MATERIAL_MASTER,
    vendor_sourcing_path: Path = DEFAULT_VENDOR_SOURCING,
) -> dict:
    shortage_event, material_by_id, fastener_candidates = _load_fastener_csv_context(
        shortage_event_path,
        material_master_path,
        vendor_sourcing_path,
    )
    target = _target_from_context(shortage_event, material_by_id)
    min_price = min(int(row["UNIT_PRICE_KRW"]) for row in fastener_candidates)
    reports = [
        evaluate_fastener_candidate(target, _candidate_from_context(candidate, material_by_id, min_price), mode=mode)
        for candidate in fastener_candidates
    ]
    return build_batch_report(reports, mode)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 3 fastener evaluation.")
    parser.add_argument("--csv-demo", action="store_true", help="Use CSV and Phase 3 fastener sample event inputs.")
    parser.add_argument("--batch", action="store_true", help="Evaluate all CSV fastener candidates and write a batch report.")
    parser.add_argument("--mode", choices=sorted(WEIGHTS), default="urgent", help="Scoring mode.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Evaluation report JSON output path.")
    parser.add_argument("--print", action="store_true", dest="print_report", help="Also print the report to stdout.")
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    if args.batch:
        report = evaluate_fastener_candidates_from_csv(mode=args.mode)
    elif args.csv_demo:
        target, candidate = load_fastener_inputs_from_csv()
        report = evaluate_fastener_candidate(target, candidate, mode=args.mode)
    else:
        target, candidate = load_sample_phase3_inputs()
        report = evaluate_fastener_candidate(target, candidate, mode=args.mode)
    write_evaluation_report(report, args.output)
    if args.print_report:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote evaluation report: {args.output}")


if __name__ == "__main__":
    main()
