"""Phase 2 web research agent with mock-first candidate collection."""

from __future__ import annotations

from datetime import datetime
import argparse
import csv
import json
from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE_INPUT = PROJECT_ROOT / ".planning" / "phase-2" / "shortage_event.sample.json"
DEFAULT_MOCK_CANDIDATES = PROJECT_ROOT / ".planning" / "phase-2" / "mock_candidates.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "candidate_results.json"

VALID_SOURCE_TYPES = {
    "manufacturer_page",
    "official_distributor",
    "industrial_marketplace",
    "marketplace",
    "unknown",
}
VALID_LOCATIONS = {"Domestic", "Overseas", "Unknown"}
VALID_SEARCH_MODES = {"mock", "live", "mixed"}

ROOT_REQUIRED_FIELDS = {
    "search_id",
    "event_id",
    "material_id",
    "material_name",
    "category",
    "target_spec_text",
    "searched_at",
    "query_used",
    "search_mode",
    "candidates",
}

CANDIDATE_REQUIRED_FIELDS = {
    "candidate_id",
    "candidate_material_id",
    "vendor_name",
    "price_krw",
    "min_price_krw",
    "lead_time_days",
    "moq",
    "location",
    "source_type",
    "source_url",
    "price_listed",
    "stock_listed",
    "leadtime_listed",
    "spec_text",
    "spec_evidence",
}


def load_shortage_event(path: str | Path) -> dict:
    """Load a Phase 1 shortage event JSON artifact."""
    event = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate_shortage_event(event)
    return event


def _validate_shortage_event(event: dict) -> None:
    required = {
        "event_id",
        "status",
        "material_id",
        "material_name",
        "category",
        "technical_specification",
        "search_keywords",
        "detected_at",
    }
    missing = sorted(required - set(event))
    if missing:
        raise ValueError(f"shortage_event is missing required fields: {', '.join(missing)}")
    if event["status"] != "SHORTAGE_DETECTED":
        raise ValueError("Phase 2 expects a SHORTAGE_DETECTED event")
    if not isinstance(event["search_keywords"], list) or len(event["search_keywords"]) < 3:
        raise ValueError("shortage_event.search_keywords must contain at least three items")


def load_mock_candidates(path: str | Path) -> list[dict]:
    """Load Phase 2-owned mock candidate rows."""
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_search_query(shortage_event: dict) -> str:
    """Build a deterministic MVP query from Phase 1 search keywords."""
    keywords = [str(item).strip() for item in shortage_event["search_keywords"] if str(item).strip()]
    if not keywords:
        return shortage_event["material_name"]
    return " ".join(keywords)


def build_candidate_results(
    shortage_event: dict,
    mock_rows: list[dict],
    search_mode: str = "mock",
    searched_at: str | None = None,
) -> dict:
    """Build a Phase 2 candidate_results payload from mock candidate rows."""
    if search_mode not in VALID_SEARCH_MODES:
        raise ValueError(f"search_mode must be one of {sorted(VALID_SEARCH_MODES)}")

    target_material_id = shortage_event["material_id"]
    rows = [row for row in mock_rows if row.get("TARGET_MATERIAL_ID") == target_material_id]
    candidates = _normalize_candidates(rows)

    return {
        "search_id": f"SR-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "event_id": shortage_event["event_id"],
        "material_id": target_material_id,
        "material_name": shortage_event["material_name"],
        "category": shortage_event["category"],
        "target_spec_text": shortage_event["technical_specification"],
        "searched_at": searched_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "query_used": build_search_query(shortage_event),
        "search_mode": search_mode,
        "candidates": candidates,
    }


def _normalize_candidates(rows: list[dict]) -> list[dict]:
    prices = [_to_int_or_none(row.get("PRICE_KRW")) for row in rows]
    non_null_prices = [price for price in prices if price is not None]
    min_price = min(non_null_prices) if non_null_prices else None

    candidates = []
    for row, price in zip(rows, prices):
        candidates.append(
            {
                "candidate_id": _required_text(row, "CANDIDATE_ID"),
                "candidate_material_id": _empty_to_none(row.get("CANDIDATE_MATERIAL_ID")),
                "vendor_name": _required_text(row, "VENDOR_NAME"),
                "price_krw": price,
                "min_price_krw": min_price,
                "lead_time_days": _to_int_or_none(row.get("LEAD_TIME_DAYS")),
                "moq": _to_int_or_none(row.get("MOQ")),
                "location": _normalize_location(row.get("LOCATION")),
                "source_type": _normalize_source_type(row.get("SOURCE_TYPE")),
                "source_url": _empty_to_none(row.get("SOURCE_URL")),
                "price_listed": _to_bool(row.get("PRICE_LISTED")),
                "stock_listed": _to_bool(row.get("STOCK_LISTED")),
                "leadtime_listed": _to_bool(row.get("LEADTIME_LISTED")),
                "spec_text": _required_text(row, "SPEC_TEXT"),
                "spec_evidence": _required_text(row, "SPEC_EVIDENCE"),
            }
        )
    return candidates


def _required_text(row: dict, field: str) -> str:
    value = str(row.get(field) or "").strip()
    if not value:
        raise ValueError(f"mock candidate row is missing {field}")
    return value


def _empty_to_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _to_int_or_none(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    return int(text)


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().upper() == "TRUE"


def _normalize_source_type(value: object) -> str:
    normalized = str(value or "unknown").strip().lower().replace(" ", "_")
    if normalized not in VALID_SOURCE_TYPES:
        return "unknown"
    return normalized


def _normalize_location(value: object) -> str:
    text = str(value or "Unknown").strip()
    return text if text in VALID_LOCATIONS else "Unknown"


def validate_candidate_results(report: dict) -> list[str]:
    """Return Phase 2 contract validation errors."""
    errors: list[str] = []
    _require_fields(report, ROOT_REQUIRED_FIELDS, "root", errors)
    if errors:
        return errors

    if report["search_mode"] not in VALID_SEARCH_MODES:
        errors.append("root.search_mode is invalid")
    if not isinstance(report["candidates"], list):
        errors.append("root.candidates must be an array")
        return errors

    for index, candidate in enumerate(report["candidates"]):
        _validate_candidate(candidate, index, errors)
    return errors


def _validate_candidate(candidate: dict, index: int, errors: list[str]) -> None:
    prefix = f"candidates[{index}]"
    if not isinstance(candidate, dict):
        errors.append(f"{prefix} must be an object")
        return

    _require_fields(candidate, CANDIDATE_REQUIRED_FIELDS, prefix, errors)
    if any(error.startswith(prefix) for error in errors):
        return

    if candidate["source_type"] not in VALID_SOURCE_TYPES:
        errors.append(f"{prefix}.source_type is invalid")
    if candidate["location"] not in VALID_LOCATIONS:
        errors.append(f"{prefix}.location is invalid")
    for field in ["price_listed", "stock_listed", "leadtime_listed"]:
        if not isinstance(candidate[field], bool):
            errors.append(f"{prefix}.{field} must be boolean")
    for field in ["price_krw", "min_price_krw", "lead_time_days", "moq"]:
        if candidate[field] is not None and not isinstance(candidate[field], int):
            errors.append(f"{prefix}.{field} must be integer or null")


def _require_fields(payload: dict, required_fields: set[str], prefix: str, errors: list[str]) -> None:
    missing = sorted(required_fields - set(payload))
    for field in missing:
        errors.append(f"{prefix}.{field} is required")


def write_candidate_results(report: dict, output_path: str | Path) -> Path:
    errors = validate_candidate_results(report)
    if errors:
        raise ValueError("candidate_results failed contract validation: " + "; ".join(errors))

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination


def run_web_research(
    input_path: str | Path = DEFAULT_SAMPLE_INPUT,
    mock_candidates_path: str | Path = DEFAULT_MOCK_CANDIDATES,
    output_path: str | Path = DEFAULT_OUTPUT,
    search_mode: str = "mock",
) -> dict:
    shortage_event = load_shortage_event(input_path)
    mock_rows = load_mock_candidates(mock_candidates_path)
    report = build_candidate_results(shortage_event, mock_rows, search_mode=search_mode)
    write_candidate_results(report, output_path)
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 2 web research candidate collection.")
    parser.add_argument("--mock-input", action="store_true", help="Use the Phase 2 sample shortage event.")
    parser.add_argument("--input", type=Path, help="Path to Phase 1 shortage_event.json.")
    parser.add_argument("--mock-candidates", type=Path, default=DEFAULT_MOCK_CANDIDATES, help="Mock candidate CSV path.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Candidate results JSON output path.")
    parser.add_argument("--search-mode", choices=sorted(VALID_SEARCH_MODES), default="mock", help="Search mode label.")
    parser.add_argument("--print", action="store_true", dest="print_report", help="Also print the report to stdout.")
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    input_path = DEFAULT_SAMPLE_INPUT if args.mock_input or not args.input else args.input
    report = run_web_research(
        input_path=input_path,
        mock_candidates_path=args.mock_candidates,
        output_path=args.output,
        search_mode=args.search_mode,
    )
    if args.print_report:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote candidate results: {args.output}")


if __name__ == "__main__":
    main()
