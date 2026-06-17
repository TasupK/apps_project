"""Phase 3 evaluation engine for generic fasteners."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import argparse
import csv
import json
from pathlib import Path
import re
import sys


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.reporting_agent import write_evaluation_report
from agents.llm_explainer import explain_candidate_decision
from tools.spec_normalizer import FastenerSpec, parse_fastener_spec


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FASTENER_SHORTAGE_EVENT = PROJECT_ROOT / ".planning" / "phase-3" / "fastener_shortage_event.sample.json"
DEFAULT_MATERIAL_MASTER = PROJECT_ROOT / "material_master.csv"
DEFAULT_VENDOR_SOURCING = PROJECT_ROOT / "vendor_sourcing.csv"
DEFAULT_CANDIDATE_RESULTS = PROJECT_ROOT / "output" / "candidate_results.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "evaluation_report.json"
DEFAULT_BATCH_OUTPUT = PROJECT_ROOT / "output" / "evaluation_report_batch.json"
SUPPORTED_PHASE2_CATEGORIES = {"Bearing", "Fastener"}


@dataclass(frozen=True)
class BearingSpec:
    bearing_code: str | None
    bearing_type: str | None
    inner_diameter_mm: int | None
    outer_diameter_mm: int | None
    width_mm: int | None
    precision_class: str | None
    material: str | None


MATERIAL_GROUPS = {
    "SUS304": ("stainless", 1),
    "SUS316": ("stainless", 2),
    "4.8": ("carbon_steel_strength", 1),
    "8.8": ("carbon_steel_strength", 2),
    "10.9": ("carbon_steel_strength", 3),
    "STEEL": ("unknown", 0),
}

MATERIAL_DECISION_RULES = {
    ("SUS304", "SUS304"): ("recommend", "Low", "원본 자재와 후보 자재의 재질이 동일합니다."),
    ("SUS304", "SUS316"): (
        "conditional_approve",
        "Medium",
        "재질이 SUS304에서 SUS316으로 상향되어 사용 가능성은 있으나 비용과 현장 조건 확인이 필요합니다.",
    ),
    ("SUS316", "SUS304"): (
        "review_required",
        "Medium",
        "재질이 SUS316에서 SUS304로 하향되어 내식성 요구조건 검토가 필요합니다.",
    ),
    ("8.8", "8.8"): ("recommend", "Low", "원본 자재와 후보 자재의 강도 등급이 동일합니다."),
    ("8.8", "10.9"): (
        "conditional_approve",
        "Medium",
        "강도 등급이 8.8에서 10.9로 상향되어 사용 가능성은 있으나 체결 조건 확인이 필요합니다.",
    ),
    ("10.9", "8.8"): ("reject", "High", "강도 등급이 10.9에서 8.8로 낮아져 대체 사용할 수 없습니다."),
    ("SUS304", "8.8"): ("reject", "High", "스테인리스 계열과 탄소강 강도 등급 계열이 달라 대체 사용할 수 없습니다."),
}

SOURCE_TYPE_BREAKDOWN = {
    "official_distributor": {"official_distributor": True, "datasheet_bonus": 30, "label": "공식 대리점"},
    "manufacturer_page": {"official_distributor": False, "datasheet_bonus": 25, "label": "제조사 공식 페이지"},
    "industrial_marketplace": {"official_distributor": False, "datasheet_bonus": 18, "label": "산업재 전문몰"},
    "marketplace": {"official_distributor": False, "datasheet_bonus": 10, "label": "일반 마켓플레이스"},
    "unknown": {"official_distributor": False, "datasheet_bonus": 0, "label": "출처 불명"},
}

WEIGHTS = {
    "normal": {
        "compatibility_score": 40,
        "vendor_trust_score": 25,
        "lead_time_score": 15,
        "price_score": 10,
        "moq_score": 5,
        "source_trust_score": 5,
    },
    "urgent": {
        "compatibility_score": 40,
        "vendor_trust_score": 25,
        "lead_time_score": 15,
        "price_score": 10,
        "moq_score": 5,
        "source_trust_score": 5,
    },
}

VENDOR_PROFILES = {
    "misumi": {
        "label": "MISUMI",
        "approved_status": "approved",
        "on_time_delivery_rate": 0.97,
        "quality_issue_rate": 0.005,
        "transaction_count": 42,
        "operational_fit": "good",
        "risk_flag": "none",
    },
    "rs-online": {
        "label": "RS Online",
        "approved_status": "approved",
        "on_time_delivery_rate": 0.94,
        "quality_issue_rate": 0.012,
        "transaction_count": 18,
        "operational_fit": "good",
        "risk_flag": "none",
    },
    "bearingworks": {
        "label": "Bearing Works",
        "approved_status": "conditional",
        "on_time_delivery_rate": 0.86,
        "quality_issue_rate": 0.025,
        "transaction_count": 7,
        "operational_fit": "partial",
        "risk_flag": "minor",
    },
    "daara": {
        "label": "Daara",
        "approved_status": "conditional",
        "on_time_delivery_rate": 0.90,
        "quality_issue_rate": 0.02,
        "transaction_count": 8,
        "operational_fit": "partial",
        "risk_flag": "minor",
    },
    "mcmaster": {
        "label": "McMaster-Carr",
        "approved_status": "approved",
        "on_time_delivery_rate": 0.96,
        "quality_issue_rate": 0.006,
        "transaction_count": 24,
        "operational_fit": "partial",
        "risk_flag": "none",
    },
}


def _snake_source_type(raw: str) -> str:
    return raw.strip().lower().replace(" ", "_")


def _bool(raw: str | bool | None) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().upper() == "TRUE"


def _optional_int(raw: object) -> int | None:
    if raw is None or raw == "":
        return None
    return int(raw)


def _material_decision(original: str | None, candidate: str | None) -> tuple[str, str, str]:
    if not original or not candidate:
        return "review_required", "High", "재질 정보가 부족하여 구매 담당자 검토가 필요합니다."

    explicit_rule = MATERIAL_DECISION_RULES.get((original, candidate))
    if explicit_rule:
        return explicit_rule

    if original == candidate:
        return "recommend", "Low", "원본 자재와 후보 자재의 재질 또는 강도 등급이 동일합니다."

    original_group, original_rank = MATERIAL_GROUPS.get(original, ("unknown", 0))
    candidate_group, candidate_rank = MATERIAL_GROUPS.get(candidate, ("unknown", 0))

    if original_group != candidate_group:
        return "reject", "High", "재질 계열이 달라 대체 사용이 어렵습니다."

    if candidate_rank > original_rank:
        return "conditional_approve", "Medium", "재질이 상향되어 사용 가능성은 있으나 비용과 현장 조건 확인이 필요합니다."

    if original_group == "carbon_steel_strength" and candidate_rank < original_rank:
        return "reject", "High", "강도 등급이 낮아져 체결 성능 리스크가 큽니다."

    return "review_required", "Medium", "재질이 하향되어 구매 담당자와 현장 검토가 필요합니다."


def _find_number(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return round(float(match.group(1)))


def _find_bearing_code(text: str) -> str | None:
    match = re.search(r"\b([67][0-9]{3,4})(?:\s*[-/]?\s*([A-Z]{1,4}[A-Z0-9/]*))?\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    suffix = match.group(2)
    if suffix:
        suffix = re.split(r"[/\s]", suffix, maxsplit=1)[0]
    return f"{match.group(1)}-{suffix.upper()}" if suffix else match.group(1)


def _base_bearing_code(code: str | None) -> str | None:
    if not code:
        return None
    match = re.match(r"([67][0-9]{3,4})", code)
    return match.group(1) if match else code


def _normalize_bearing_type(text: str, bearing_code: str | None = None) -> str | None:
    lowered = text.lower()
    if "angular contact" in lowered or "앵귤러" in lowered or "앵글러" in lowered:
        return "angular_contact"
    base_code = _base_bearing_code(bearing_code)
    if base_code and base_code.startswith("7"):
        return "angular_contact"
    if "deep groove" in lowered or "6200" in lowered or "ball bearing" in lowered or "볼 베어링" in lowered:
        return "deep_groove_ball"
    return None


def _normalize_bearing_precision(text: str) -> str | None:
    match = re.search(r"\b(P[0-9][A-Z]?|P4S|CLASS\s*[0-9]|ABEC\s*-?\s*[0-9])\b", text, flags=re.IGNORECASE)
    return match.group(1).upper().replace(" ", "") if match else None


def _normalize_bearing_material(text: str) -> str | None:
    lowered = text.lower()
    if "stainless" in lowered or "sus" in lowered:
        return "STAINLESS"
    if "steel" in lowered or "스틸" in lowered or "강" in lowered:
        return "STEEL"
    return None


def parse_bearing_spec(text: str) -> BearingSpec:
    compact = " ".join(str(text or "").split())
    bearing_code = _find_bearing_code(compact)
    dimension_match = re.search(
        r"\b([0-9]+(?:\.[0-9]+)?)\s*(?:mm)?\s*[xX×]\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mm)?\s*[xX×]\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mm)?\b",
        compact,
        flags=re.IGNORECASE,
    )
    if dimension_match:
        inner_diameter = round(float(dimension_match.group(1)))
        outer_diameter = round(float(dimension_match.group(2)))
        width = round(float(dimension_match.group(3)))
    else:
        inner_diameter = _find_number(r"\b([0-9]+(?:\.[0-9]+)?)\s*mm\s*(?:ID|I\.D\.|inner diameter|bore)\b", compact)
        if inner_diameter is None:
            inner_diameter = _find_number(r"\b(?:ID|I\.D\.|inner diameter|bore)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*mm\b", compact)
        outer_diameter = _find_number(r"\b([0-9]+(?:\.[0-9]+)?)\s*mm\s*(?:OD|O\.D\.|outer diameter)\b", compact)
        if outer_diameter is None:
            outer_diameter = _find_number(r"\b(?:OD|O\.D\.|outer diameter)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*mm\b", compact)
        width = _find_number(r"\b([0-9]+(?:\.[0-9]+)?)\s*mm\s*(?:Width|Race Width|W)\b", compact)
        if width is None:
            width = _find_number(r"\b(?:Width|Race Width|W)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*mm\b", compact)

    return BearingSpec(
        bearing_code=bearing_code,
        bearing_type=_normalize_bearing_type(compact, bearing_code),
        inner_diameter_mm=inner_diameter,
        outer_diameter_mm=outer_diameter,
        width_mm=width,
        precision_class=_normalize_bearing_precision(compact),
        material=_normalize_bearing_material(compact),
    )


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
        "diameter": "직경이 달라 체결 호환이 어렵습니다.",
        "pitch": "피치가 달라 나사산 체결이 불가능할 수 있습니다.",
        "thread_system": "규격 체계가 달라 호환이 어렵습니다.",
        "length_mm": "길이가 달라 조립 간섭 또는 체결 깊이 문제가 발생할 수 있습니다.",
        "material": "재질 차이로 내식성, 강도, 비용에 영향이 있을 수 있습니다.",
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


def _source_trust_breakdown(candidate: dict) -> tuple[dict, int, dict]:
    source_type = _infer_candidate_source_type(candidate)
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
    score += 10 if candidate.get("source_url") or candidate.get("SOURCE_URL") else 0
    score = min(score, 100)
    return breakdown, score, _source_trust_notes(source_meta["label"], breakdown, score)


def _infer_candidate_source_type(candidate: dict) -> str:
    source_type = _snake_source_type(candidate.get("source_type") or candidate.get("SOURCE_TYPE", "unknown"))
    if source_type != "unknown":
        return source_type

    text = " ".join(
        str(candidate.get(field) or "")
        for field in ["source_url", "SOURCE_URL", "vendor_name", "VENDOR_NAME"]
    ).lower()
    if any(token in text for token in ["misumi", "rs-online", "rs online", "mcmaster", "digikey", "mouser"]):
        return "official_distributor"
    if any(token in text for token in ["bearingworks", "industrial", "daara"]):
        return "industrial_marketplace"
    if any(token in text for token in ["amazon", "ebay", "aliexpress", "made-in-china"]):
        return "marketplace"
    return "unknown"


def _source_trust_notes(source_label: str, breakdown: dict, score: int) -> dict:
    positive_factors = [f"출처 유형이 '{source_label}'로 분류되었습니다."]
    risk_factors = []

    if breakdown["official_distributor"]:
        positive_factors.append("공식 판매처로 확인되어 출처 신뢰도가 높습니다.")
    else:
        risk_factors.append("공식 판매처 여부가 확인되지 않았습니다.")

    if breakdown["datasheet_available"]:
        positive_factors.append("규격 근거 텍스트가 충분하여 스펙 확인 가능성이 높습니다.")
    else:
        risk_factors.append("데이터시트 또는 상세 규격 근거가 부족합니다.")

    for field, positive_message, risk_message in [
        ("stock_visible", "재고 표시가 확인되었습니다.", "재고 표시가 없어 실제 구매 가능 여부 확인이 필요합니다."),
        ("price_visible", "가격 표시가 확인되었습니다.", "가격 표시가 없어 견적 확인이 필요합니다."),
        ("leadtime_visible", "납기 표시가 확인되었습니다.", "납기 표시가 없어 긴급 발주 적합성 확인이 필요합니다."),
    ]:
        if breakdown[field]:
            positive_factors.append(positive_message)
        else:
            risk_factors.append(risk_message)

    if score >= 80:
        summary = "출처 신뢰도가 높아 자동 추천 근거로 사용할 수 있습니다."
    elif score >= 50:
        summary = "출처 신뢰도는 보통 수준이며 주요 표시 정보 확인이 필요합니다."
    else:
        summary = "출처 신뢰도가 낮아 자동 추천보다 사람 검토가 필요합니다."

    return {
        "summary": summary,
        "positive_factors": positive_factors,
        "risk_factors": risk_factors,
    }


def _vendor_trust_breakdown(candidate: dict) -> tuple[dict, int, dict]:
    profile = _vendor_profile(candidate)
    breakdown = {
        "vendor_label": profile["label"],
        "approved_status": profile["approved_status"],
        "approved_status_score": _approved_status_score(profile["approved_status"]),
        "delivery_reliability_score": _delivery_reliability_score(profile.get("on_time_delivery_rate")),
        "quality_performance_score": _quality_performance_score(profile.get("quality_issue_rate")),
        "transaction_maturity_score": _transaction_maturity_score(profile.get("transaction_count")),
        "operational_fit_score": _operational_fit_score(profile.get("operational_fit")),
        "risk_flag_score": _risk_flag_score(profile.get("risk_flag")),
        "on_time_delivery_rate": profile.get("on_time_delivery_rate"),
        "quality_issue_rate": profile.get("quality_issue_rate"),
        "transaction_count": profile.get("transaction_count"),
        "operational_fit": profile.get("operational_fit"),
        "risk_flag": profile.get("risk_flag"),
    }
    score = sum(
        breakdown[field]
        for field in [
            "approved_status_score",
            "delivery_reliability_score",
            "quality_performance_score",
            "transaction_maturity_score",
            "operational_fit_score",
            "risk_flag_score",
        ]
    )
    return breakdown, score, _vendor_trust_notes(profile["label"], breakdown, score)


def _vendor_profile(candidate: dict) -> dict:
    explicit_status = candidate.get("vendor_approved_status") or candidate.get("VENDOR_APPROVED_STATUS")
    if explicit_status:
        return {
            "label": candidate.get("vendor_name") or candidate.get("VENDOR_NAME") or "Explicit vendor",
            "approved_status": str(explicit_status).strip().lower(),
            "on_time_delivery_rate": _optional_float(candidate.get("on_time_delivery_rate") or candidate.get("ON_TIME_DELIVERY_RATE")),
            "quality_issue_rate": _optional_float(candidate.get("quality_issue_rate") or candidate.get("QUALITY_ISSUE_RATE")),
            "transaction_count": _optional_int(candidate.get("transaction_count") or candidate.get("TRANSACTION_COUNT")),
            "operational_fit": str(candidate.get("operational_fit") or candidate.get("OPERATIONAL_FIT") or "unknown").strip().lower(),
            "risk_flag": str(candidate.get("risk_flag") or candidate.get("RISK_FLAG") or "unknown").strip().lower(),
        }

    text = " ".join(
        str(candidate.get(field) or "")
        for field in ["vendor_name", "VENDOR_NAME", "source_url", "SOURCE_URL"]
    ).lower()
    for key, profile in VENDOR_PROFILES.items():
        if key in text:
            return dict(profile)
    return {
        "label": candidate.get("vendor_name") or candidate.get("VENDOR_NAME") or "Unknown Vendor",
        "approved_status": "unknown",
        "on_time_delivery_rate": None,
        "quality_issue_rate": None,
        "transaction_count": None,
        "operational_fit": "unknown",
        "risk_flag": "unknown",
    }


def _optional_float(raw: object) -> float | None:
    if raw is None or raw == "":
        return None
    return float(raw)


def _approved_status_score(status: str | None) -> int:
    return {
        "approved": 25,
        "conditional": 15,
        "new": 8,
        "unknown": 5,
        "blocked": 0,
    }.get(str(status or "unknown").strip().lower(), 5)


def _delivery_reliability_score(rate: float | None) -> int:
    if rate is None:
        return 10
    if rate >= 0.95:
        return 25
    if rate >= 0.90:
        return 20
    if rate >= 0.80:
        return 12
    return 5


def _quality_performance_score(rate: float | None) -> int:
    if rate is None:
        return 10
    if rate < 0.01:
        return 25
    if rate <= 0.03:
        return 18
    if rate <= 0.05:
        return 10
    return 3


def _transaction_maturity_score(count: int | None) -> int:
    if count is None:
        return 2
    if count >= 20:
        return 10
    if count >= 5:
        return 7
    if count >= 1:
        return 4
    return 2


def _operational_fit_score(fit: str | None) -> int:
    return {
        "good": 10,
        "partial": 6,
        "poor": 3,
        "unknown": 5,
    }.get(str(fit or "unknown").strip().lower(), 5)


def _risk_flag_score(flag: str | None) -> int:
    return {
        "none": 5,
        "minor": 2,
        "unknown": 2,
        "major": 0,
        "blocked": 0,
    }.get(str(flag or "unknown").strip().lower(), 2)


def _vendor_trust_notes(vendor_label: str, breakdown: dict, score: int) -> dict:
    positive_factors = []
    risk_factors = []

    if breakdown["approved_status"] == "approved":
        positive_factors.append("내부 승인 벤더 또는 신뢰 가능한 기존 공급처로 분류되었습니다.")
    elif breakdown["approved_status"] == "conditional":
        risk_factors.append("조건부 승인 벤더라 거래 조건 확인이 필요합니다.")
    elif breakdown["approved_status"] == "blocked":
        risk_factors.append("차단 벤더로 자동 발주할 수 없습니다.")
    else:
        risk_factors.append("내부 승인 벤더 여부가 확인되지 않았습니다.")

    if breakdown["delivery_reliability_score"] >= 20:
        positive_factors.append("정시 납품 이력이 양호합니다.")
    else:
        risk_factors.append("정시 납품 이력이 부족하거나 낮습니다.")

    if breakdown["quality_performance_score"] >= 18:
        positive_factors.append("품질 이슈율이 낮은 편입니다.")
    else:
        risk_factors.append("품질 이슈 데이터가 부족하거나 주의가 필요합니다.")

    if breakdown["risk_flag_score"] == 5:
        positive_factors.append("중대한 공급사 리스크 플래그가 없습니다.")
    else:
        risk_factors.append("공급사 리스크 플래그 확인이 필요합니다.")

    if score >= 75:
        summary = f"{vendor_label} 공급사 신뢰도가 높아 자동 승인 후보로 검토할 수 있습니다."
    elif score >= 60:
        summary = f"{vendor_label} 공급사 신뢰도는 조건부 승인 수준입니다."
    else:
        summary = f"{vendor_label} 공급사 신뢰도가 낮거나 데이터가 부족해 수동 검토가 필요합니다."

    return {
        "summary": summary,
        "positive_factors": positive_factors,
        "risk_factors": risk_factors,
    }


def _lead_time_score(days: int | None) -> int:
    if days is None:
        return 35
    if days <= 1:
        return 100
    if days <= 3:
        return 85
    if days <= 7:
        return 65
    if days <= 14:
        return 45
    return 20


def _price_score(price: int | None, min_price: int | None) -> int:
    if price is None or min_price is None or price <= 0 or min_price <= 0:
        return 40
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
    vendor_trust_score: int,
    vendor_trust_breakdown: dict,
    differences: list[dict],
) -> dict:
    decision, risk_level, reason_seed = material_decision
    if critical_check["critical_mismatch"]:
        return {
            "decision": "reject",
            "risk_level": "High",
            "recommendation_reason": "필수 규격이 일치하지 않아 대체재로 추천하지 않습니다.",
            "approval_conditions": [],
            "rejection_reason": "직경, 피치, 규격 체계, 길이 중 하나 이상의 필수 스펙이 불일치합니다.",
            "review_required": False,
        }

    if vendor_trust_breakdown.get("approved_status") == "blocked" or vendor_trust_breakdown.get("risk_flag") == "blocked":
        return {
            "decision": "reject",
            "risk_level": "High",
            "recommendation_reason": "공급사가 차단 또는 고위험 벤더로 분류되어 자동 발주할 수 없습니다.",
            "approval_conditions": [],
            "rejection_reason": "공급사 신뢰도 게이트를 통과하지 못했습니다.",
            "review_required": False,
        }

    if vendor_trust_score < 60 and decision != "reject":
        return {
            "decision": "review_required",
            "risk_level": "High",
            "recommendation_reason": "스펙은 유사하지만 공급사 신뢰도가 낮거나 데이터가 부족해 자동 추천할 수 없습니다.",
            "approval_conditions": [],
            "rejection_reason": None,
            "review_required": True,
        }

    if source_trust_score < 50 and decision != "reject":
        return {
            "decision": "review_required",
            "risk_level": "High",
            "recommendation_reason": "규격은 유사하지만 출처 신뢰도가 낮아 자동 추천할 수 없습니다.",
            "approval_conditions": [],
            "rejection_reason": None,
            "review_required": True,
        }

    approval_conditions = []
    if decision == "conditional_approve" and any(item["spec"] == "material" for item in differences):
        approval_conditions.append("재질 대체에 따른 비용 증가와 내식성 요구조건 충족 여부를 확인해야 합니다.")
    if vendor_trust_score < 75 and decision in {"recommend", "conditional_approve"}:
        decision = "conditional_approve"
        risk_level = "Medium"
        approval_conditions.append("공급사 신뢰도가 조건부 승인 구간이라 구매 담당자 확인이 필요합니다.")

    return {
        "decision": decision,
        "risk_level": risk_level,
        "recommendation_reason": reason_seed,
        "approval_conditions": approval_conditions,
        "rejection_reason": None,
        "review_required": decision == "review_required",
    }


def _bearing_critical_spec_check(original: BearingSpec, candidate: BearingSpec) -> dict:
    base_code_match = (
        _base_bearing_code(original.bearing_code) is not None
        and _base_bearing_code(original.bearing_code) == _base_bearing_code(candidate.bearing_code)
    )
    dimension_fields = ["inner_diameter_mm", "outer_diameter_mm", "width_mm"]
    dimension_matches = {
        f"{field}_match": getattr(original, field) is not None
        and getattr(candidate, field) is not None
        and getattr(original, field) == getattr(candidate, field)
        for field in dimension_fields
    }
    dimension_values_present = all(getattr(original, field) is not None and getattr(candidate, field) is not None for field in dimension_fields)
    dimensions_match = all(dimension_matches.values())
    type_match = (
        original.bearing_type is not None
        and candidate.bearing_type is not None
        and original.bearing_type == candidate.bearing_type
    )
    precision_match = (
        original.precision_class is not None
        and candidate.precision_class is not None
        and original.precision_class == candidate.precision_class
    )
    precision_grade_match = (
        _bearing_precision_grade(original.precision_class) is not None
        and _bearing_precision_grade(original.precision_class) == _bearing_precision_grade(candidate.precision_class)
    )

    critical_mismatch = (
        (dimension_values_present and not dimensions_match)
        or (
            original.bearing_type is not None
            and candidate.bearing_type is not None
            and original.bearing_type != candidate.bearing_type
        )
        or (
            original.precision_class is not None
            and candidate.precision_class is not None
            and original.precision_class != candidate.precision_class
            and not precision_grade_match
        )
    )
    original_has_dimensions = all(getattr(original, field) is not None for field in dimension_fields)
    incomplete_critical_specs = not (
        (dimensions_match if original_has_dimensions else base_code_match)
        and (type_match or original.bearing_type is None or candidate.bearing_type is None)
    )

    return {
        "base_code_match": base_code_match,
        "inner_diameter_match": dimension_matches["inner_diameter_mm_match"],
        "outer_diameter_match": dimension_matches["outer_diameter_mm_match"],
        "width_match": dimension_matches["width_mm_match"],
        "dimensions_match": dimensions_match,
        "type_match": type_match,
        "precision_match": precision_match,
        "precision_grade_match": precision_grade_match,
        "critical_mismatch": critical_mismatch,
        "incomplete_critical_specs": incomplete_critical_specs,
    }


def _bearing_precision_grade(precision_class: str | None) -> str | None:
    if not precision_class:
        return None
    match = re.search(r"P([0-9])", precision_class.upper())
    return match.group(1) if match else precision_class.upper()


def _highlight_bearing_differences(original: BearingSpec, candidate: BearingSpec) -> list[dict]:
    impacts = {
        "bearing_code": "베어링 기본 형번이 다르면 치수와 구조 호환성 확인이 필요합니다.",
        "bearing_type": "베어링 형식이 달라 하중 방향과 장착 조건이 달라질 수 있습니다.",
        "inner_diameter_mm": "내경이 달라 샤프트에 장착할 수 없습니다.",
        "outer_diameter_mm": "외경이 달라 하우징에 장착할 수 없습니다.",
        "width_mm": "폭이 달라 조립 간섭 또는 고정 문제가 발생할 수 있습니다.",
        "precision_class": "정밀도 등급이 달라 고속/정밀 장비 적용 전 검토가 필요합니다.",
        "material": "재질 정보 차이로 내식성 또는 수명 조건 검토가 필요합니다.",
    }
    differences = []
    for field_name, impact in impacts.items():
        original_value = getattr(original, field_name)
        candidate_value = getattr(candidate, field_name)
        if original_value is not None and candidate_value is not None and original_value != candidate_value:
            differences.append(
                {
                    "spec": field_name,
                    "original": original_value,
                    "candidate": candidate_value,
                    "impact": impact,
                }
            )
    return differences


def _bearing_material_decision(original: BearingSpec, candidate: BearingSpec, critical_check: dict) -> tuple[str, str, str]:
    if critical_check["critical_mismatch"]:
        return "reject", "High", "베어링 핵심 치수, 형식 또는 정밀도 등급이 일치하지 않습니다."
    if critical_check["incomplete_critical_specs"]:
        return "review_required", "Medium", "일부 핵심 베어링 스펙이 부족해 구매 담당자 확인이 필요합니다."
    if original.material and candidate.material and original.material != candidate.material:
        return "conditional_approve", "Medium", "치수와 형식은 맞지만 재질 차이가 있어 사용 조건 확인이 필요합니다."
    if original.precision_class and candidate.precision_class and original.precision_class != candidate.precision_class:
        return "conditional_approve", "Medium", "정밀도 등급 계열은 같지만 세부 접미사가 달라 적용 장비 조건 확인이 필요합니다."
    if original.precision_class and not candidate.precision_class:
        return "conditional_approve", "Medium", "치수와 형식은 맞지만 후보의 정밀도 등급 확인이 필요합니다."
    return "recommend", "Low", "베어링 형번 또는 핵심 치수와 형식이 원본 자재와 일치합니다."


def _bearing_compatibility_score(critical_check: dict, material_decision: str) -> int:
    if critical_check["critical_mismatch"]:
        return 0
    if material_decision == "recommend":
        return 100
    if material_decision == "conditional_approve":
        return 86
    if material_decision == "review_required":
        return 68
    return 20


def _bearing_decision_context(
    critical_check: dict,
    material_decision: tuple[str, str, str],
    source_trust_score: int,
    vendor_trust_score: int,
    vendor_trust_breakdown: dict,
    differences: list[dict],
) -> dict:
    decision, risk_level, reason_seed = material_decision
    if critical_check["critical_mismatch"]:
        return {
            "decision": "reject",
            "risk_level": "High",
            "recommendation_reason": "베어링 핵심 스펙이 일치하지 않아 대체재로 추천하지 않습니다.",
            "approval_conditions": [],
            "rejection_reason": "내경, 외경, 폭, 형식, 정밀도 중 확인된 핵심 스펙이 불일치합니다.",
            "review_required": False,
        }
    if vendor_trust_breakdown.get("approved_status") == "blocked" or vendor_trust_breakdown.get("risk_flag") == "blocked":
        return {
            "decision": "reject",
            "risk_level": "High",
            "recommendation_reason": "공급사가 차단 또는 고위험 벤더로 분류되어 자동 발주할 수 없습니다.",
            "approval_conditions": [],
            "rejection_reason": "공급사 신뢰도 게이트를 통과하지 못했습니다.",
            "review_required": False,
        }
    if vendor_trust_score < 60 and decision in {"recommend", "conditional_approve"}:
        return {
            "decision": "review_required",
            "risk_level": "High",
            "recommendation_reason": "베어링 스펙은 유사하지만 공급사 신뢰도가 낮거나 데이터가 부족해 자동 추천할 수 없습니다.",
            "approval_conditions": [],
            "rejection_reason": None,
            "review_required": True,
        }
    if source_trust_score < 50 and decision in {"recommend", "conditional_approve"}:
        return {
            "decision": "review_required",
            "risk_level": "High",
            "recommendation_reason": "베어링 스펙은 유사하지만 출처 신뢰도가 낮아 자동 추천할 수 없습니다.",
            "approval_conditions": [],
            "rejection_reason": None,
            "review_required": True,
        }

    approval_conditions = []
    if decision == "conditional_approve":
        approval_conditions = [item["impact"] for item in differences] or ["정밀도 등급, 재질, 적용 장비 조건을 확인해야 합니다."]
    if vendor_trust_score < 75 and decision in {"recommend", "conditional_approve"}:
        decision = "conditional_approve"
        risk_level = "Medium"
        approval_conditions.append("공급사 신뢰도가 조건부 승인 구간이라 구매 담당자 확인이 필요합니다.")

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
    trust_breakdown, source_trust_score, source_trust_notes = _source_trust_breakdown(candidate_material)
    vendor_trust_breakdown, vendor_trust_score, vendor_trust_notes = _vendor_trust_breakdown(candidate_material)

    scores = {
        "compatibility_score": _compatibility_score(critical_check, material_decision[0]),
        "vendor_trust_score": vendor_trust_score,
        "source_trust_score": source_trust_score,
        "lead_time_score": _lead_time_score(candidate_material["lead_time_days"]),
        "price_score": _price_score(candidate_material["price_krw"], candidate_material["min_price_krw"]),
        "moq_score": _moq_score(candidate_material.get("moq")),
    }
    scores["final_score"] = _weighted_total(scores, mode)

    decision_context = _decision_context(
        critical_check,
        material_decision,
        source_trust_score,
        vendor_trust_score,
        vendor_trust_breakdown,
        differences,
    )

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
            "price_krw": candidate_material["price_krw"],
            "lead_time_days": candidate_material["lead_time_days"],
            "moq": candidate_material.get("moq"),
            "spec": asdict(candidate_spec),
        },
        "spec_analysis": {
            "critical_spec_check": critical_check,
            "highlighted_differences": differences,
        },
        "scores": scores,
        "source_trust_breakdown": trust_breakdown,
        "source_trust_notes": source_trust_notes,
        "vendor_trust_breakdown": vendor_trust_breakdown,
        "vendor_trust_notes": vendor_trust_notes,
        "decision_context": decision_context,
    }


def evaluate_bearing_candidate(
    target_material: dict,
    candidate_material: dict,
    mode: str = "normal",
) -> dict:
    target_spec = parse_bearing_spec(target_material["spec_text"])
    candidate_spec = parse_bearing_spec(candidate_material["spec_text"])

    critical_check = _bearing_critical_spec_check(target_spec, candidate_spec)
    material_decision = _bearing_material_decision(target_spec, candidate_spec, critical_check)
    differences = _highlight_bearing_differences(target_spec, candidate_spec)
    trust_breakdown, source_trust_score, source_trust_notes = _source_trust_breakdown(candidate_material)
    vendor_trust_breakdown, vendor_trust_score, vendor_trust_notes = _vendor_trust_breakdown(candidate_material)

    scores = {
        "compatibility_score": _bearing_compatibility_score(critical_check, material_decision[0]),
        "vendor_trust_score": vendor_trust_score,
        "source_trust_score": source_trust_score,
        "lead_time_score": _lead_time_score(candidate_material["lead_time_days"]),
        "price_score": _price_score(candidate_material["price_krw"], candidate_material["min_price_krw"]),
        "moq_score": _moq_score(candidate_material.get("moq")),
    }
    scores["final_score"] = _weighted_total(scores, mode)
    decision_context = _bearing_decision_context(
        critical_check,
        material_decision,
        source_trust_score,
        vendor_trust_score,
        vendor_trust_breakdown,
        differences,
    )

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
            "price_krw": candidate_material["price_krw"],
            "lead_time_days": candidate_material["lead_time_days"],
            "moq": candidate_material.get("moq"),
            "spec": asdict(candidate_spec),
        },
        "spec_analysis": {
            "critical_spec_check": critical_check,
            "highlighted_differences": differences,
        },
        "scores": scores,
        "source_trust_breakdown": trust_breakdown,
        "source_trust_notes": source_trust_notes,
        "vendor_trust_breakdown": vendor_trust_breakdown,
        "vendor_trust_notes": vendor_trust_notes,
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


def _target_from_candidate_results(candidate_results: dict) -> dict:
    return {
        "material_id": candidate_results["material_id"],
        "description": candidate_results["material_name"],
        "spec_text": f"{candidate_results['material_name']} {candidate_results['target_spec_text']}",
    }


def _candidate_from_phase2_result(candidate: dict, min_price: int | None) -> dict:
    return {
        "candidate_id": candidate["candidate_id"],
        "vendor_name": candidate["vendor_name"],
        "source_url": candidate.get("source_url"),
        "source_type": candidate.get("source_type") or "unknown",
        "price_krw": _optional_int(candidate.get("price_krw")),
        "min_price_krw": min_price,
        "lead_time_days": _optional_int(candidate.get("lead_time_days")),
        "moq": _optional_int(candidate.get("moq")),
        "spec_text": candidate["spec_text"],
        "SPEC_EVIDENCE": candidate.get("spec_evidence", ""),
        "PRICE_LISTED": candidate.get("price_listed", False),
        "STOCK_LISTED": candidate.get("stock_listed", False),
        "LEADTIME_LISTED": candidate.get("leadtime_listed", False),
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
            1 if report["candidate_material"].get("price_krw") is None else 0,
            _decision_priority(report["decision_context"]["decision"]),
            -report["scores"]["final_score"],
        ),
    )
    for report in sorted_reports:
        report["llm_explanation"] = explain_candidate_decision(report)

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


def evaluate_candidates_from_phase2_results(
    candidate_results_path: Path = DEFAULT_CANDIDATE_RESULTS,
    mode: str = "urgent",
) -> dict:
    candidate_results = json.loads(candidate_results_path.read_text(encoding="utf-8"))
    candidates = candidate_results.get("candidates", [])
    if not candidates:
        return build_batch_report([], mode)

    if candidate_results.get("category") and candidate_results.get("category") not in SUPPORTED_PHASE2_CATEGORIES:
        return _unsupported_category_batch_report(candidate_results, mode)

    target = _target_from_candidate_results(candidate_results)
    known_prices = [
        int(candidate["price_krw"])
        for candidate in candidates
        if candidate.get("price_krw") not in {None, ""}
    ]
    min_price = min(known_prices) if known_prices else None
    evaluator = evaluate_bearing_candidate if candidate_results.get("category") == "Bearing" else evaluate_fastener_candidate
    reports = [
        evaluator(target, _candidate_from_phase2_result(candidate, min_price), mode=mode)
        for candidate in candidates
    ]
    return build_batch_report(reports, mode)


def _unsupported_category_batch_report(candidate_results: dict, mode: str) -> dict:
    category = candidate_results.get("category") or "Unknown"
    items = []
    for candidate in candidate_results.get("candidates", []):
        items.append(
            {
                "report_id": f"ER-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "mode": mode,
                "target_material": {
                    "material_id": candidate_results.get("material_id"),
                    "description": candidate_results.get("material_name"),
                    "spec": {"raw_text": candidate_results.get("target_spec_text")},
                },
                "candidate_material": {
                    "candidate_id": candidate.get("candidate_id"),
                    "vendor_name": candidate.get("vendor_name"),
                    "source_url": candidate.get("source_url"),
                    "source_type": _snake_source_type(candidate.get("source_type") or "unknown"),
                    "price_krw": _optional_int(candidate.get("price_krw")),
                    "lead_time_days": _optional_int(candidate.get("lead_time_days")),
                    "moq": _optional_int(candidate.get("moq")),
                    "spec": {"raw_text": candidate.get("spec_text")},
                },
                "spec_analysis": {
                    "critical_spec_check": {
                        "critical_mismatch": False,
                        "reason": f"Phase 3 automatic evaluator does not support category: {category}.",
                    },
                    "highlighted_differences": [],
                },
                "scores": {
                    "compatibility_score": 0,
                    "vendor_trust_score": 0,
                    "source_trust_score": 0,
                    "lead_time_score": 0,
                    "price_score": 0,
                    "moq_score": 0,
                    "final_score": 0,
                },
                "source_trust_breakdown": {},
                "source_trust_notes": {
                    "summary": "자동 평가 범위 밖의 카테고리입니다.",
                    "positive_factors": [],
                    "risk_factors": [f"{category} 카테고리는 현재 fastener 평가 규칙으로 검증하지 않습니다."],
                },
                "vendor_trust_breakdown": {},
                "vendor_trust_notes": {
                    "summary": "지원하지 않는 카테고리라 공급사 신뢰도를 자동 평가하지 않았습니다.",
                    "positive_factors": [],
                    "risk_factors": ["공급사 신뢰도 수동 확인이 필요합니다."],
                },
                "decision_context": {
                    "decision": "review_required",
                    "risk_level": "High",
                    "recommendation_reason": "지원하지 않는 카테고리라 구매 담당자 수동 검토가 필요합니다.",
                    "approval_conditions": [],
                    "rejection_reason": None,
                    "review_required": True,
                },
            }
        )
    return build_batch_report(items, mode)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 3 fastener evaluation.")
    parser.add_argument("--csv-demo", action="store_true", help="Use CSV and Phase 3 fastener sample event inputs.")
    parser.add_argument("--batch", action="store_true", help="Evaluate all CSV fastener candidates and write a batch report.")
    parser.add_argument("--candidate-results", type=Path, help="Evaluate Phase 2 candidate_results.json output.")
    parser.add_argument("--mode", choices=sorted(WEIGHTS), default="urgent", help="Scoring mode.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Evaluation report JSON output path.")
    parser.add_argument("--print", action="store_true", dest="print_report", help="Also print the report to stdout.")
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()
    if args.candidate_results:
        report = evaluate_candidates_from_phase2_results(args.candidate_results, mode=args.mode)
    elif args.batch:
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
