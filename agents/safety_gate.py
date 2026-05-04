"""Phase 3 safety gate helpers."""

from __future__ import annotations


def requires_manual_review(report: dict) -> bool:
    return bool(report["decision_context"]["review_required"])


def is_rejected(report: dict) -> bool:
    return report["decision_context"]["decision"] == "reject"


def can_auto_recommend(report: dict) -> bool:
    return report["decision_context"]["decision"] == "recommend"
