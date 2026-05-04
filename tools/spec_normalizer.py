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


def _find(pattern: str, text: str) -> re.Match[str] | None:
    return re.search(pattern, text, flags=re.IGNORECASE)


def _normalize_material(text: str) -> str | None:
    for material, pattern in MATERIAL_PATTERNS.items():
        if _find(pattern, text):
            return material
    return None


def _normalize_thread_system(text: str) -> str | None:
    if _find(r"\b(?:metric|m\d+)\b", text):
        return "Metric"
    if _find(r"\b(?:unc|unf|un)\b", text):
        return "UNC"
    return None


def parse_fastener_spec(text: str) -> FastenerSpec:
    diameter_match = _find(r"\b(M\d+)\b", text)
    pitch_match = _find(r"(?:thread pitch|pitch)\s*([0-9]+(?:\.[0-9]+)?)", text)
    length_match = _find(r"length\s*([0-9]+)\s*mm", text)

    return FastenerSpec(
        diameter=diameter_match.group(1).upper() if diameter_match else None,
        pitch=pitch_match.group(1) if pitch_match else None,
        length_mm=int(length_match.group(1)) if length_match else None,
        thread_system=_normalize_thread_system(text),
        material=_normalize_material(text),
    )
