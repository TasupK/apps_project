import json
import unittest
from pathlib import Path

from agents.evaluation_agent import build_batch_report, evaluate_fastener_candidate
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
FASTENER_SAMPLE_INPUT = PROJECT_ROOT / ".planning" / "phase-2" / "fastener_shortage_event.sample.json"
FASTENER_SAMPLE_OUTPUT = PROJECT_ROOT / ".planning" / "phase-2" / "candidate_results.fastener.sample.json"


class Phase2ContractTests(unittest.TestCase):
    def test_sample_output_matches_phase2_contract(self):
        report = json.loads(SAMPLE_OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual(validate_candidate_results(report), [])

    def test_fastener_sample_output_matches_phase2_contract(self):
        report = json.loads(FASTENER_SAMPLE_OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual(validate_candidate_results(report), [])

    def test_generated_output_matches_phase2_contract(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, load_mock_candidates(DEFAULT_MOCK_CANDIDATES))
        self.assertEqual(validate_candidate_results(report), [])

    def test_generated_fastener_output_matches_phase2_contract(self):
        shortage_event = load_shortage_event(FASTENER_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, load_mock_candidates(DEFAULT_MOCK_CANDIDATES))
        self.assertEqual(validate_candidate_results(report), [])
        self.assertEqual(report["material_id"], "MAT-3001")
        self.assertEqual([candidate["candidate_id"] for candidate in report["candidates"]], ["WEB-005", "WEB-006", "WEB-007", "WEB-008"])

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

    def test_fastener_output_can_flow_into_phase3_evaluation(self):
        shortage_event = load_shortage_event(FASTENER_SAMPLE_INPUT)
        phase2_report = build_candidate_results(shortage_event, load_mock_candidates(DEFAULT_MOCK_CANDIDATES))
        target = {
            "material_id": phase2_report["material_id"],
            "description": phase2_report["material_name"],
            "spec_text": phase2_report["target_spec_text"],
        }
        phase3_reports = [
            evaluate_fastener_candidate(target, _phase3_candidate_from_phase2(candidate), mode="urgent")
            for candidate in phase2_report["candidates"]
        ]
        batch = build_batch_report(phase3_reports, mode="urgent")
        decisions = {
            item["candidate_material"]["candidate_id"]: item["decision_context"]["decision"]
            for item in batch["items"]
        }
        self.assertEqual(batch["next_action"], "approval_pending")
        self.assertEqual(batch["top_candidate_id"], "WEB-006")
        self.assertEqual(decisions["WEB-005"], "reject")
        self.assertEqual(decisions["WEB-006"], "recommend")
        self.assertEqual(decisions["WEB-007"], "conditional_approve")
        self.assertEqual(decisions["WEB-008"], "review_required")


def _phase3_candidate_from_phase2(candidate: dict) -> dict:
    return {
        "candidate_id": candidate["candidate_id"],
        "vendor_name": candidate["vendor_name"],
        "source_url": candidate["source_url"],
        "source_type": candidate["source_type"],
        "price_krw": candidate["price_krw"],
        "min_price_krw": candidate["min_price_krw"],
        "lead_time_days": candidate["lead_time_days"],
        "moq": candidate["moq"],
        "spec_text": candidate["spec_text"],
        "SPEC_EVIDENCE": candidate["spec_evidence"],
        "PRICE_LISTED": candidate["price_listed"],
        "STOCK_LISTED": candidate["stock_listed"],
        "LEADTIME_LISTED": candidate["leadtime_listed"],
    }


if __name__ == "__main__":
    unittest.main()
