"""Phase 3 helpers for parsing generic fastener specifications."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class FastenerSpec:
    diameter: str | None
    pitch: str | None
    length_mm: int | None
    thread_system: str | None
    material: str | None


MATERIAL_PATTERNS = {
    "SUS316": r"\b(?:sus\s*316|stainless steel\s*316|316)\b",
    "SUS304": r"\b(?:sus\s*304|stainless steel\s*304|304)\b",
    "10.9": r"\b10\.9\b",
    "8.8": r"\b8\.8\b",
    "4.8": r"\b4\.8\b",
    "STEEL": r"\bsteel\b",
}


MM_PER_INCH = 25.4


def _find(pattern: str, text: str) -> re.Match[str] | None:
    return re.search(pattern, text, flags=re.IGNORECASE)


def _normalize_material(text: str) -> str | None:
    for material, pattern in MATERIAL_PATTERNS.items():
        if _find(pattern, text):
            return material
    return None


def _normalize_thread_system(text: str) -> str | None:
    if _find(r"\bmetric\b|\bM\s*[0-9]+(?:\.[0-9]+)?(?=\b|[-xX])", text):
        return "Metric"
    if _find(r"\b(?:unc|unf|un|[0-9]+/[0-9]+\s*-\s*[0-9]+)\b", text):
        return "UNC"
    return None


def _normalize_metric_diameter(text: str) -> str | None:
    match = _find(r"\bM\s*([0-9]+(?:\.[0-9]+)?)(?=\b|[-xX])", text)
    if not match:
        return None
    number = match.group(1)
    if number.endswith(".0"):
        number = number[:-2]
    return f"M{number}"


def _normalize_unc_diameter(text: str) -> str | None:
    match = _find(r"\b([0-9]+/[0-9]+)\s*-\s*([0-9]+)\b", text)
    return match.group(1) if match else None


def _normalize_pitch(text: str, thread_system: str | None) -> str | None:
    if thread_system == "UNC":
        unc_match = _find(r"\b[0-9]+/[0-9]+\s*-\s*([0-9]+)\b", text)
        return unc_match.group(1) if unc_match else None

    explicit_match = _find(r"(?:thread pitch|pitch|p)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)", text)
    if explicit_match:
        return explicit_match.group(1)

    compact_match = _find(r"\bM\s*[0-9]+(?:\.[0-9]+)?\s*[-xX]\s*([0-9]+(?:\.[0-9]+)?)\s*[xX]\s*[0-9]+", text)
    return compact_match.group(1) if compact_match else None


def _normalize_length_mm(text: str, thread_system: str | None) -> int | None:
    length_mm_match = _find(r"(?:length|len|l)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*mm\b", text)
    if length_mm_match:
        return round(float(length_mm_match.group(1)))

    compact_metric_match = _find(
        r"\bM\s*[0-9]+(?:\.[0-9]+)?(?:\s*[-xX]\s*[0-9]+(?:\.[0-9]+)?)?\s*[xX]\s*([0-9]+(?:\.[0-9]+)?)\s*(?:mm)?\b",
        text,
    )
    if compact_metric_match:
        return round(float(compact_metric_match.group(1)))

    unc_length_match = _find(
        r"\b[0-9]+/[0-9]+\s*-\s*[0-9]+\s*(?:unc|unf|un)?\s*[xX]\s*([0-9]+(?:\.[0-9]+)?)\s*(?:in|inch|inches|\"|”)?\b",
        text,
    )
    if unc_length_match and thread_system == "UNC":
        return round(float(unc_length_match.group(1)) * MM_PER_INCH)

    return None


def parse_fastener_spec(text: str) -> FastenerSpec:
    thread_system = _normalize_thread_system(text)
    diameter = _normalize_metric_diameter(text) if thread_system != "UNC" else _normalize_unc_diameter(text)

    return FastenerSpec(
        diameter=diameter,
        pitch=_normalize_pitch(text, thread_system),
        length_mm=_normalize_length_mm(text, thread_system),
        thread_system=thread_system,
        material=_normalize_material(text),
    )
