import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agents.evaluation_agent import (
    build_batch_report,
    evaluate_fastener_candidate,
    evaluate_fastener_candidates_from_csv,
    load_fastener_inputs_from_csv,
)
from agents.reporting_agent import write_evaluation_report
from tools.spec_normalizer import parse_fastener_spec


def build_candidate(spec_text: str, source_type: str = "official_distributor") -> dict:
    return {
        "candidate_id": "CAND-001",
        "vendor_name": "Vendor",
        "source_url": "https://example.com/item",
        "source_type": source_type,
        "price_krw": 450,
        "min_price_krw": 450,
        "lead_time_days": 1,
        "moq": 10,
        "spec_text": spec_text,
        "SPEC_EVIDENCE": "Datasheet available with metric dimensions and material grade.",
        "PRICE_LISTED": True,
        "STOCK_LISTED": True,
        "LEADTIME_LISTED": True,
    }


TARGET = {
    "material_id": "BT-H-M10-50",
    "description": "Hex bolt",
    "spec_text": "Hex head bolt M10 thread pitch 1.5 length 50mm. Stainless steel 304.",
}


class Phase3EvaluationTests(unittest.TestCase):
    def test_parse_fastener_spec(self):
        parsed = parse_fastener_spec("Hex head bolt M10 thread pitch 1.5 length 50mm. Stainless steel 304.")
        self.assertEqual(parsed.diameter, "M10")
        self.assertEqual(parsed.pitch, "1.5")
        self.assertEqual(parsed.length_mm, 50)
        self.assertEqual(parsed.thread_system, "Metric")
        self.assertEqual(parsed.material, "SUS304")

    def test_parse_compact_metric_spec_without_pitch(self):
        parsed = parse_fastener_spec("SUS304 Hex Socket Bolt M10x50 L50mm")
        self.assertEqual(parsed.diameter, "M10")
        self.assertEqual(parsed.pitch, None)
        self.assertEqual(parsed.length_mm, 50)
        self.assertEqual(parsed.thread_system, "Metric")
        self.assertEqual(parsed.material, "SUS304")

    def test_parse_compact_metric_spec_with_pitch(self):
        parsed = parse_fastener_spec("SUS316 cap screw M10-1.5x50")
        self.assertEqual(parsed.diameter, "M10")
        self.assertEqual(parsed.pitch, "1.5")
        self.assertEqual(parsed.length_mm, 50)
        self.assertEqual(parsed.thread_system, "Metric")
        self.assertEqual(parsed.material, "SUS316")

    def test_parse_metric_spec_with_p_prefix(self):
        parsed = parse_fastener_spec("Steel bolt M8 P1.25 L25mm strength class 8.8")
        self.assertEqual(parsed.diameter, "M8")
        self.assertEqual(parsed.pitch, "1.25")
        self.assertEqual(parsed.length_mm, 25)
        self.assertEqual(parsed.thread_system, "Metric")
        self.assertEqual(parsed.material, "8.8")

    def test_parse_unc_spec_and_convert_length_to_mm(self):
        parsed = parse_fastener_spec('Hex bolt 1/4-20 UNC x 1" steel')
        self.assertEqual(parsed.diameter, "1/4")
        self.assertEqual(parsed.pitch, "20")
        self.assertEqual(parsed.length_mm, 25)
        self.assertEqual(parsed.thread_system, "UNC")
        self.assertEqual(parsed.material, "STEEL")

    def test_reject_on_diameter_mismatch(self):
        candidate = build_candidate("Hex head bolt M8 thread pitch 1.5 length 50mm. Stainless steel 304.")
        report = evaluate_fastener_candidate(TARGET, candidate)
        self.assertEqual(report["decision_context"]["decision"], "reject")

    def test_reject_on_pitch_mismatch(self):
        candidate = build_candidate("Hex head bolt M10 thread pitch 1.25 length 50mm. Stainless steel 304.")
        report = evaluate_fastener_candidate(TARGET, candidate)
        self.assertEqual(report["decision_context"]["decision"], "reject")

    def test_reject_on_length_mismatch(self):
        candidate = build_candidate("Hex head bolt M10 thread pitch 1.5 length 45mm. Stainless steel 304.")
        report = evaluate_fastener_candidate(TARGET, candidate)
        self.assertEqual(report["decision_context"]["decision"], "reject")

    def test_conditional_approve_on_material_upgrade(self):
        candidate = build_candidate("Hex head bolt M10 thread pitch 1.5 length 50mm. Stainless steel 316.")
        report = evaluate_fastener_candidate(TARGET, candidate)
        self.assertEqual(report["decision_context"]["decision"], "conditional_approve")

    def test_review_required_on_stainless_downgrade(self):
        target = {
            "material_id": "BT-H-M10-50",
            "description": "Hex bolt",
            "spec_text": "Hex head bolt M10 thread pitch 1.5 length 50mm. Stainless steel 316.",
        }
        candidate = build_candidate("Hex head bolt M10 thread pitch 1.5 length 50mm. Stainless steel 304.")
        report = evaluate_fastener_candidate(target, candidate)
        self.assertEqual(report["decision_context"]["decision"], "review_required")

    def test_reject_on_material_group_mismatch(self):
        candidate = build_candidate("Hex head bolt M10 thread pitch 1.5 length 50mm. Steel 8.8.")
        report = evaluate_fastener_candidate(TARGET, candidate)
        self.assertEqual(report["decision_context"]["decision"], "reject")

    def test_load_fastener_inputs_from_csv(self):
        target, candidate = load_fastener_inputs_from_csv()
        self.assertEqual(target["material_id"], "MAT-3001")
        self.assertIn("length 50mm", target["spec_text"])
        self.assertEqual(candidate["candidate_id"], "WEB-005")
        self.assertIn("length 55mm", candidate["spec_text"])

    def test_write_evaluation_report(self):
        candidate = build_candidate("Hex head bolt M10 thread pitch 1.5 length 50mm. Stainless steel 316.")
        report = evaluate_fastener_candidate(TARGET, candidate)
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "evaluation_report.json"
            written_path = write_evaluation_report(report, output_path)
            self.assertTrue(written_path.exists())
            self.assertIn("conditional_approve", written_path.read_text(encoding="utf-8"))

    def test_build_batch_report_sorts_viable_before_rejected(self):
        rejected = evaluate_fastener_candidate(
            TARGET,
            build_candidate("Hex head bolt M10 thread pitch 1.5 length 45mm. Stainless steel 304."),
        )
        conditional = evaluate_fastener_candidate(
            TARGET,
            build_candidate("Hex head bolt M10 thread pitch 1.5 length 50mm. Stainless steel 316."),
        )
        batch = build_batch_report([rejected, conditional], mode="urgent")
        self.assertEqual(batch["top_candidate_id"], "CAND-001")
        self.assertEqual(batch["next_action"], "approval_pending")
        self.assertEqual(batch["items"][0]["decision_context"]["decision"], "conditional_approve")

    def test_evaluate_fastener_candidates_from_csv(self):
        batch = evaluate_fastener_candidates_from_csv()
        self.assertEqual(batch["candidate_count"], 4)
        self.assertEqual(batch["next_action"], "approval_pending")
        self.assertEqual(batch["top_candidate_id"], "WEB-006")
        decisions = {
            item["candidate_material"]["candidate_id"]: item["decision_context"]["decision"]
            for item in batch["items"]
        }
        self.assertEqual(decisions["WEB-006"], "recommend")
        self.assertEqual(decisions["WEB-007"], "conditional_approve")
        self.assertEqual(decisions["WEB-008"], "review_required")
        self.assertEqual(decisions["WEB-005"], "reject")


if __name__ == "__main__":
    unittest.main()
