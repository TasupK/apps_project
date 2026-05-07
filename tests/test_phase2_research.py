import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from agents.web_research_agent import (
    DEFAULT_MOCK_CANDIDATES,
    DEFAULT_SAMPLE_INPUT,
    build_candidate_results,
    build_search_query,
    load_mock_candidates,
    load_shortage_event,
    run_web_research,
    validate_candidate_results,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Phase2ResearchTests(unittest.TestCase):
    def test_load_phase1_sample_input(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        self.assertEqual(shortage_event["material_id"], "MAT-1001")
        self.assertEqual(shortage_event["status"], "SHORTAGE_DETECTED")
        self.assertGreaterEqual(len(shortage_event["search_keywords"]), 3)

    def test_query_generation_uses_search_keywords(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        query = build_search_query(shortage_event)
        self.assertIn("Ball Bearing 6204-ZZ", query)
        self.assertIn("20mm 47mm 14mm", query)
        self.assertIn("replacement", query)

    def test_mock_candidates_return_at_least_two_items(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, load_mock_candidates(DEFAULT_MOCK_CANDIDATES))
        self.assertGreaterEqual(len(report["candidates"]), 2)

    def test_root_material_id_stays_phase1_shortage_material(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, load_mock_candidates(DEFAULT_MOCK_CANDIDATES))
        self.assertEqual(report["material_id"], "MAT-1001")
        self.assertTrue(all(candidate["candidate_material_id"] == "MAT-1002" for candidate in report["candidates"]))

    def test_candidates_include_required_normalized_fields(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, load_mock_candidates(DEFAULT_MOCK_CANDIDATES))
        first = report["candidates"][0]
        self.assertEqual(first["candidate_id"], "WEB-001")
        self.assertEqual(first["source_type"], "official_distributor")
        self.assertIsInstance(first["price_listed"], bool)
        self.assertIsInstance(first["stock_listed"], bool)
        self.assertIsInstance(first["leadtime_listed"], bool)
        self.assertIn("6204", first["spec_text"])
        self.assertIn("datasheet", first["spec_evidence"].lower())

    def test_missing_url_is_null_and_missing_price_is_null(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, load_mock_candidates(DEFAULT_MOCK_CANDIDATES))
        quick_supply = next(candidate for candidate in report["candidates"] if candidate["candidate_id"] == "WEB-004")
        self.assertIsNone(quick_supply["source_url"])
        self.assertIsNone(quick_supply["price_krw"])
        self.assertFalse(quick_supply["price_listed"])

    def test_min_price_is_lowest_non_null_candidate_price(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, load_mock_candidates(DEFAULT_MOCK_CANDIDATES))
        self.assertTrue(all(candidate["min_price_krw"] == 9000 for candidate in report["candidates"]))

    def test_run_web_research_writes_output(self):
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "candidate_results.json"
            report = run_web_research(output_path=output_path)
            written = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(written["search_id"], report["search_id"])
            self.assertEqual(validate_candidate_results(written), [])


if __name__ == "__main__":
    unittest.main()
