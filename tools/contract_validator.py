"""Shared contract checks for Phase 3 handoff artifacts."""

from __future__ import annotations


VALID_MODES = {"normal", "urgent"}
VALID_DECISIONS = {"recommend", "conditional_approve", "review_required", "reject"}
VALID_NEXT_ACTIONS = {"approval_pending", "manual_review", "no_viable_candidate"}
VALID_RISK_LEVELS = {"Low", "Medium", "High"}

BATCH_REQUIRED_FIELDS = {
    "batch_report_id",
    "generated_at",
    "mode",
    "candidate_count",
    "decision_counts",
    "top_candidate_id",
    "next_action",
    "items",
}

ITEM_REQUIRED_FIELDS = {
    "report_id",
    "generated_at",
    "mode",
    "target_material",
    "candidate_material",
    "spec_analysis",
    "scores",
    "source_trust_breakdown",
    "decision_context",
}

DECISION_CONTEXT_REQUIRED_FIELDS = {
    "decision",
    "risk_level",
    "recommendation_reason",
    "approval_conditions",
    "rejection_reason",
    "review_required",
}


def validate_batch_report(report: dict) -> list[str]:
    """Return contract validation errors for a Phase 3 batch report."""
    errors: list[str] = []

    _require_fields(report, BATCH_REQUIRED_FIELDS, "batch", errors)
    if errors:
        return errors

    _validate_batch_root(report, errors)
    if isinstance(report["items"], list):
        for index, item in enumerate(report["items"]):
            _validate_item(item, index, errors)

    _validate_counts(report, errors)
    _validate_next_action(report, errors)
    return errors


def _require_fields(payload: dict, required_fields: set[str], prefix: str, errors: list[str]) -> None:
    missing = sorted(required_fields - set(payload))
    for field in missing:
        errors.append(f"{prefix}.{field} is required")


def _validate_batch_root(report: dict, errors: list[str]) -> None:
    if report["mode"] not in VALID_MODES:
        errors.append(f"batch.mode must be one of {sorted(VALID_MODES)}")

    if not isinstance(report["candidate_count"], int) or report["candidate_count"] < 0:
        errors.append("batch.candidate_count must be a non-negative integer")

    if report["next_action"] not in VALID_NEXT_ACTIONS:
        errors.append(f"batch.next_action must be one of {sorted(VALID_NEXT_ACTIONS)}")

    if not isinstance(report["decision_counts"], dict):
        errors.append("batch.decision_counts must be an object")

    if not isinstance(report["items"], list):
        errors.append("batch.items must be an array")


def _validate_item(item: dict, index: int, errors: list[str]) -> None:
    prefix = f"items[{index}]"
    if not isinstance(item, dict):
        errors.append(f"{prefix} must be an object")
        return

    _require_fields(item, ITEM_REQUIRED_FIELDS, prefix, errors)
    if any(error.startswith(prefix) for error in errors):
        return

    if item["mode"] not in VALID_MODES:
        errors.append(f"{prefix}.mode must be one of {sorted(VALID_MODES)}")

    decision_context = item["decision_context"]
    _require_fields(decision_context, DECISION_CONTEXT_REQUIRED_FIELDS, f"{prefix}.decision_context", errors)
    if any(error.startswith(f"{prefix}.decision_context") for error in errors):
        return

    if decision_context["decision"] not in VALID_DECISIONS:
        errors.append(f"{prefix}.decision_context.decision is invalid")

    if decision_context["risk_level"] not in VALID_RISK_LEVELS:
        errors.append(f"{prefix}.decision_context.risk_level is invalid")

    if not isinstance(decision_context["approval_conditions"], list):
        errors.append(f"{prefix}.decision_context.approval_conditions must be an array")

    if not isinstance(decision_context["review_required"], bool):
        errors.append(f"{prefix}.decision_context.review_required must be boolean")


def _validate_counts(report: dict, errors: list[str]) -> None:
    if not isinstance(report["decision_counts"], dict) or not isinstance(report["items"], list):
        return

    actual_counts: dict[str, int] = {}
    for item in report["items"]:
        decision_context = item.get("decision_context", {})
        decision = decision_context.get("decision")
        if decision:
            actual_counts[decision] = actual_counts.get(decision, 0) + 1

    if report["candidate_count"] != len(report["items"]):
        errors.append("batch.candidate_count must match length of items")

    if report["decision_counts"] != actual_counts:
        errors.append("batch.decision_counts must match item decisions")


def _validate_next_action(report: dict, errors: list[str]) -> None:
    if not isinstance(report["items"], list):
        return

    decisions = {
        item.get("decision_context", {}).get("decision")
        for item in report["items"]
    }
    if {"recommend", "conditional_approve"} & decisions:
        expected = "approval_pending"
    elif "review_required" in decisions:
        expected = "manual_review"
    else:
        expected = "no_viable_candidate"

    if report["next_action"] != expected:
        errors.append(f"batch.next_action must be {expected}")
