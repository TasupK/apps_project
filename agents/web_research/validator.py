from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from .config import *

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
