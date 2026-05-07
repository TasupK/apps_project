import json
import unittest
from pathlib import Path

from agents.web_research_agent import (
    DEFAULT_MOCK_CANDIDATES,
    DEFAULT_SAMPLE_INPUT,
    VALID_SOURCE_TYPES,
    build_candidate_results,
    load_mock_candidates,
    load_shortage_event,
    validate_candidate_results,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_OUTPUT = PROJECT_ROOT / ".planning" / "phase-2" / "candidate_results.sample.json"


class Phase2ContractTests(unittest.TestCase):
    def test_sample_output_matches_phase2_contract(self):
        report = json.loads(SAMPLE_OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual(validate_candidate_results(report), [])

    def test_generated_output_matches_phase2_contract(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, load_mock_candidates(DEFAULT_MOCK_CANDIDATES))
        self.assertEqual(validate_candidate_results(report), [])

    def test_source_type_uses_phase3_snake_case_enum(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, load_mock_candidates(DEFAULT_MOCK_CANDIDATES))
        for candidate in report["candidates"]:
            self.assertIn(candidate["source_type"], VALID_SOURCE_TYPES)
            self.assertEqual(candidate["source_type"], candidate["source_type"].lower())
            self.assertNotIn(" ", candidate["source_type"])

    def test_missing_required_candidate_field_is_reported(self):
        report = json.loads(SAMPLE_OUTPUT.read_text(encoding="utf-8"))
        del report["candidates"][0]["spec_text"]
        self.assertIn("candidates[0].spec_text is required", validate_candidate_results(report))

    def test_candidate_boolean_fields_must_be_real_booleans(self):
        report = json.loads(SAMPLE_OUTPUT.read_text(encoding="utf-8"))
        report["candidates"][0]["price_listed"] = "TRUE"
        self.assertIn("candidates[0].price_listed must be boolean", validate_candidate_results(report))

    def test_root_material_id_must_not_be_candidate_material_id(self):
        report = json.loads(SAMPLE_OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual(report["material_id"], "MAT-1001")
        self.assertNotEqual(report["material_id"], report["candidates"][0]["candidate_material_id"])


if __name__ == "__main__":
    unittest.main()
