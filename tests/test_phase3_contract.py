import json
import unittest
from pathlib import Path

from agents.evaluation_agent import evaluate_fastener_candidates_from_csv
from tools.contract_validator import validate_batch_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_BATCH_REPORT = PROJECT_ROOT / ".planning" / "shared" / "contracts" / "evaluation_report_batch.sample.json"
SCHEMA_FILE = PROJECT_ROOT / ".planning" / "shared" / "contracts" / "evaluation_report_batch.schema.json"


class Phase3ContractTests(unittest.TestCase):
    def test_shared_sample_report_matches_contract(self):
        report = json.loads(SAMPLE_BATCH_REPORT.read_text(encoding="utf-8"))
        self.assertEqual(validate_batch_report(report), [])

    def test_generated_batch_report_matches_contract(self):
        report = evaluate_fastener_candidates_from_csv()
        self.assertEqual(validate_batch_report(report), [])

    def test_contract_schema_file_is_valid_json(self):
        schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
        self.assertEqual(schema["title"], "Phase 3 Evaluation Batch Report")

    def test_next_action_must_match_item_decisions(self):
        report = json.loads(SAMPLE_BATCH_REPORT.read_text(encoding="utf-8"))
        report["next_action"] = "no_viable_candidate"
        errors = validate_batch_report(report)
        self.assertIn("batch.next_action must be approval_pending", errors)


if __name__ == "__main__":
    unittest.main()
