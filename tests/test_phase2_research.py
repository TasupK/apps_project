import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import agents.web_research_agent as web_research_agent
from agents.web_research_agent import (
    DEFAULT_SAMPLE_INPUT,
    build_candidate_results,
    build_deterministic_query_candidates,
    build_search_query,
    collect_search_results,
    generate_query_candidates,
    get_verified_search_results,
    get_exchange_rate_to_krw,
    extract_candidate_details,
    extract_candidate_details_from_text,
    fetch_page_text,
    load_shortage_event,
    make_search_result,
    _canonical_url,
    _filter_relevant_search_results,
    _merge_candidate_details,
    _parse_candidate_detail_response,
    _parse_llm_query_response,
    _rank_search_results,
    run_web_research,
    search_web,
    validate_candidate_results,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Phase2ResearchTests(unittest.TestCase):
    def setUp(self):
        self._original_search_web = web_research_agent.search_web
        self._original_fetch_page_text = web_research_agent.fetch_page_text
        self._original_extract_candidate_details = web_research_agent.extract_candidate_details
        self._original_get_exchange_rate_to_krw = web_research_agent.get_exchange_rate_to_krw

    def tearDown(self):
        web_research_agent.search_web = self._original_search_web
        web_research_agent.fetch_page_text = self._original_fetch_page_text
        web_research_agent.extract_candidate_details = self._original_extract_candidate_details
        web_research_agent.get_exchange_rate_to_krw = self._original_get_exchange_rate_to_krw

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

    def test_deterministic_query_candidates_include_research_intent(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        queries = build_deterministic_query_candidates(shortage_event)
        self.assertGreaterEqual(len(queries), 3)
        self.assertIn("Ball Bearing 6204-ZZ", queries[0])
        self.assertTrue(any("official datasheet price stock" in query for query in queries))
        self.assertTrue(any("replacement alternative" in query for query in queries))
        self.assertTrue(any("대체품 호환품 가격 재고 납기" in query for query in queries))

    def test_llm_query_generation_falls_back_without_api_key(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        self.assertEqual(
            generate_query_candidates(shortage_event, query_mode="llm", api_key=""),
            build_deterministic_query_candidates(shortage_event),
        )

    def test_llm_query_generation_keeps_stable_queries_first(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        original_generate_with_llm = web_research_agent._llm_client.generate_query_candidates_with_llm
        web_research_agent._llm_client.generate_query_candidates_with_llm = lambda *_args, **_kwargs: [
            "6204-ZZ alternate supplier price",
        ]
        try:
            queries = generate_query_candidates(shortage_event, query_mode="llm", api_key="fake")
        finally:
            web_research_agent._llm_client.generate_query_candidates_with_llm = original_generate_with_llm

        self.assertEqual(queries[0], build_deterministic_query_candidates(shortage_event)[0])
        self.assertIn("6204-ZZ alternate supplier price", queries)

    def test_parse_llm_query_response_supports_responses_output_shape(self):
        response_body = {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "queries": [
                                        "6204-ZZ bearing official distributor price stock",
                                        "6204-2RS replacement 20mm 47mm 14mm lead time",
                                    ]
                                }
                            ),
                        }
                    ]
                }
            ]
        }
        queries = _parse_llm_query_response(response_body)
        self.assertEqual(queries[0], "6204-ZZ bearing official distributor price stock")
        self.assertEqual(len(queries), 2)

    def test_fetch_page_text_strips_script_and_style(self):
        class FakeResponse:
            headers = {"Content-Type": "text/html; charset=utf-8"}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self, _size):
                return b"<html><style>.x{}</style><script>bad()</script><body>Price KRW 15000 <b>Ships in 1 day</b></body></html>"

        original_urlopen = web_research_agent.urllib.request.urlopen
        web_research_agent.urllib.request.urlopen = lambda _request, timeout=20: FakeResponse()
        try:
            text = fetch_page_text("https://example.com/product")
        finally:
            web_research_agent.urllib.request.urlopen = original_urlopen
        self.assertIn("Price KRW 15000", text)
        self.assertIn("Ships in 1 day", text)
        self.assertNotIn("bad()", text)

    def test_parse_candidate_detail_response_normalizes_contract_fields(self):
        response_body = {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "vendor_name": "MISUMI Korea",
                                    "price_krw": 15000,
                                    "raw_price_text": "15,000원",
                                    "listed_price": 15000,
                                    "listed_currency": "KRW",
                                    "lead_time_days": 1,
                                    "moq": None,
                                    "location": "Domestic",
                                    "source_type": "official_distributor",
                                    "price_listed": True,
                                    "stock_listed": True,
                                    "leadtime_listed": True,
                                    "spec_text": "6204-ZZ bearing 20mm ID 47mm OD 14mm width steel.",
                                    "spec_evidence": "Page table lists 20mm ID, 47mm OD, 14mm width, steel.",
                                }
                            ),
                        }
                    ]
                }
            ]
        }
        details = _parse_candidate_detail_response(response_body)
        self.assertEqual(details["vendor_name"], "MISUMI Korea")
        self.assertEqual(details["price_krw"], 15000)
        self.assertEqual(details["lead_time_days"], 1)
        self.assertTrue(details["stock_listed"])

    def test_parse_candidate_detail_response_converts_foreign_price_to_krw(self):
        web_research_agent.get_exchange_rate_to_krw = lambda currency: 1350.0 if currency == "USD" else None
        response_body = {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "vendor_name": "Motion Canada",
                                    "price_krw": None,
                                    "raw_price_text": "$17.94",
                                    "listed_price": 17.94,
                                    "listed_currency": "USD",
                                    "lead_time_days": None,
                                    "moq": None,
                                    "location": "Overseas",
                                    "source_type": "unknown",
                                    "price_listed": True,
                                    "stock_listed": True,
                                    "leadtime_listed": False,
                                    "spec_text": "NSK 6204ZZ bearing.",
                                    "spec_evidence": "Page lists $17.94 and in stock.",
                                }
                            ),
                        }
                    ]
                }
            ]
        }
        details = _parse_candidate_detail_response(response_body)
        self.assertEqual(details["price_krw"], 24219)
        self.assertIn("Converted listed price", details["spec_evidence"])

    def test_merge_candidate_details_keeps_unknowns_when_missing(self):
        candidate = {
            "candidate_id": "LIVE-001",
            "vendor_name": "Search Result Vendor",
            "price_krw": None,
            "lead_time_days": None,
            "moq": None,
            "location": "Unknown",
            "source_type": "unknown",
            "spec_text": "snippet",
            "spec_evidence": "snippet evidence",
            "price_listed": False,
            "stock_listed": False,
            "leadtime_listed": False,
        }
        merged = _merge_candidate_details(
            candidate,
            {
                "vendor_name": "MISUMI Korea",
                "price_krw": 15000,
                "lead_time_days": 1,
                "price_listed": True,
                "stock_listed": True,
                "leadtime_listed": True,
                "spec_text": "page spec",
                "spec_evidence": "page evidence",
            },
        )
        self.assertEqual(merged["vendor_name"], "MISUMI Korea")
        self.assertEqual(merged["price_krw"], 15000)
        self.assertEqual(merged["spec_evidence"], "page evidence")

    def test_extract_candidate_details_none_mode_returns_empty(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        self.assertEqual(extract_candidate_details({}, "Price KRW 15000", shortage_event), {})

    def test_text_extraction_detects_usd_price_and_stock(self):
        web_research_agent.get_exchange_rate_to_krw = lambda currency: 1350.0 if currency == "USD" else None
        details = extract_candidate_details_from_text("Price $30.18 /each In Stock Add to Cart")
        self.assertEqual(details["price_krw"], 40743)
        self.assertTrue(details["price_listed"])
        self.assertTrue(details["stock_listed"])

    def test_text_extraction_detects_lead_time_and_moq(self):
        details = extract_candidate_details_from_text("Usually ships within 2 business days. MOQ: 10")
        self.assertEqual(details["lead_time_days"], 2)
        self.assertEqual(details["moq"], 10)
        self.assertTrue(details["leadtime_listed"])

    def test_llm_plan_search_result_is_not_verified(self):
        results = search_web("6204-ZZ bearing distributor", provider="llm_plan")
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["verified"])
        self.assertIsNone(results[0]["url"])

    def test_collect_search_results_dedupes_verified_urls(self):
        result = make_search_result(
            query="6204-ZZ",
            title="6204-2RS Bearing - MISUMI Korea",
            url="https://example.com/misumi/6204-2rs",
            snippet="20mm ID 47mm OD 14mm width",
            source_type_hint="official_distributor",
            verified=True,
        )
        verified = get_verified_search_results([result, {**result, "query": "duplicate query"}])
        self.assertEqual(len(verified), 2)

        collected = collect_search_results(["6204-ZZ", "6204-ZZ"], provider="llm_plan")
        self.assertEqual(len(collected), 1)
        self.assertEqual(get_verified_search_results(collected), [])

    def test_canonical_url_removes_tracking_query_params(self):
        first = "https://kr.misumi-ec.com/vona2/detail/221005276386/?HissuCode=6204ZZ&srsltid=AAA&utm_source=x"
        second = "https://kr.misumi-ec.com/vona2/detail/221005276386/?HissuCode=6204ZZ&srsltid=BBB"
        self.assertEqual(_canonical_url(first), _canonical_url(second))

    def test_search_result_ranking_prioritizes_purchase_signals(self):
        catalog = make_search_result(
            query="6204-ZZ",
            title="6204-ZZ catalog dimensions",
            url="https://example.com/catalog/6204zz",
            snippet="Dimensions and specifications only.",
            source_type_hint="manufacturer_page",
            verified=True,
        )
        purchasable = make_search_result(
            query="6204-ZZ",
            title="Buy 6204-ZZ Bearing - MISUMI",
            url="https://example.com/buy/6204zz",
            snippet="Price, stock, ships today.",
            source_type_hint="official_distributor",
            verified=True,
        )
        ranked = _rank_search_results([catalog, purchasable])
        self.assertEqual(ranked[0]["url"], "https://example.com/buy/6204zz")

    def test_relevance_filter_keeps_results_anchored_to_shortage_material(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        relevant = make_search_result(
            query="6204-ZZ",
            title="Buy 6204-ZZ Bearing - MISUMI",
            url="https://example.com/buy/6204zz",
            snippet="20mm ID 47mm OD 14mm width steel.",
            source_type_hint="official_distributor",
            verified=True,
        )
        unrelated = make_search_result(
            query="6204-ZZ",
            title="Buy HSR20 linear guide - MISUMI",
            url="https://example.com/buy/hsr20",
            snippet="Price, stock, ships today.",
            source_type_hint="official_distributor",
            verified=True,
        )

        filtered = _filter_relevant_search_results([unrelated, relevant], shortage_event)
        self.assertEqual(filtered, [relevant])

    def test_live_mode_without_provider_does_not_promote_llm_plan_to_candidate(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(
            shortage_event,
            search_mode="live",
            search_provider="llm_plan",
        )
        self.assertEqual(report["search_mode"], "live")
        self.assertEqual(report["candidates"], [])
        self.assertEqual(validate_candidate_results(report), [])

    def test_search_provider_requires_api_key(self):
        existing_key = os.environ.pop("SERPAPI_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                search_web("6204-ZZ bearing distributor", provider="serpapi")
        finally:
            if existing_key is not None:
                os.environ["SERPAPI_API_KEY"] = existing_key

    def test_live_search_results_return_candidate_stubs(self):
        web_research_agent.search_web = _fake_verified_search_web
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, search_mode="live", search_provider="serpapi")
        self.assertGreaterEqual(len(report["candidates"]), 2)

    def test_live_search_does_not_promote_unrelated_material(self):
        web_research_agent.search_web = _fake_mixed_material_search_web
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, search_mode="live", search_provider="serpapi")
        self.assertEqual(len(report["candidates"]), 1)
        self.assertIn("6204", report["candidates"][0]["spec_text"])

    def test_live_search_limits_promoted_candidates(self):
        web_research_agent.search_web = _fake_many_verified_search_web
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(
            shortage_event,
            search_mode="live",
            search_provider="serpapi",
            max_candidates=3,
        )
        self.assertEqual(len(report["candidates"]), 3)
        self.assertEqual(report["candidates"][-1]["candidate_id"], "LIVE-003")

    def test_root_material_id_stays_phase1_shortage_material(self):
        web_research_agent.search_web = _fake_verified_search_web
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, search_mode="live", search_provider="serpapi")
        self.assertEqual(report["material_id"], "MAT-1001")
        self.assertTrue(all(candidate["candidate_material_id"] is None for candidate in report["candidates"]))

    def test_candidates_include_required_normalized_fields(self):
        web_research_agent.search_web = _fake_verified_search_web
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, search_mode="live", search_provider="serpapi")
        first = report["candidates"][0]
        self.assertEqual(first["candidate_id"], "LIVE-001")
        self.assertEqual(first["source_type"], "official_distributor")
        self.assertIsInstance(first["price_listed"], bool)
        self.assertIsInstance(first["stock_listed"], bool)
        self.assertIsInstance(first["leadtime_listed"], bool)
        self.assertIn("6204", first["spec_text"])
        self.assertIn("verified search result", first["spec_evidence"].lower())

    def test_llm_plan_results_are_not_promoted_to_candidates(self):
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, search_mode="live", search_provider="llm_plan")
        self.assertEqual(report["candidates"], [])
        self.assertEqual(validate_candidate_results(report), [])

    def test_live_candidate_stubs_keep_unknown_values_null_or_false(self):
        web_research_agent.search_web = _fake_verified_search_web
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(shortage_event, search_mode="live", search_provider="serpapi")
        first = report["candidates"][0]
        self.assertIsNone(first["price_krw"])
        self.assertIsNone(first["lead_time_days"])
        self.assertIsNone(first["min_price_krw"])
        self.assertFalse(first["price_listed"])
        self.assertFalse(first["stock_listed"])
        self.assertFalse(first["leadtime_listed"])

    def test_llm_extraction_enriches_live_candidate_stubs(self):
        web_research_agent.search_web = _fake_verified_search_web
        web_research_agent.fetch_page_text = lambda _url: "Price KRW 15000. Ships in 1 day. In stock. 6204-ZZ 20mm 47mm 14mm steel."
        web_research_agent.extract_candidate_details = _fake_extract_candidate_details
        shortage_event = load_shortage_event(DEFAULT_SAMPLE_INPUT)
        report = build_candidate_results(
            shortage_event,
            search_mode="live",
            search_provider="serpapi",
            extraction_mode="llm",
        )
        first = report["candidates"][0]
        self.assertEqual(first["price_krw"], 15000)
        self.assertEqual(first["min_price_krw"], 15000)
        self.assertEqual(first["lead_time_days"], 1)
        self.assertTrue(first["price_listed"])
        self.assertIn("page table", first["spec_evidence"])

    def test_run_web_research_writes_output(self):
        web_research_agent.search_web = _fake_verified_search_web
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "candidate_results.json"
            report = run_web_research(output_path=output_path, search_provider="serpapi")
            written = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(written["search_id"], report["search_id"])
            self.assertEqual(validate_candidate_results(written), [])


def _fake_verified_search_web(query: str, provider: str | None = None, max_results: int = 5):
    return [
        make_search_result(
            query=query,
            title="6204-ZZ Ball Bearing - MISUMI Korea",
            url="https://example.com/misumi/6204-zz",
            snippet="20mm ID, 47mm OD, 14mm width, steel bearing.",
            source_type_hint="official_distributor",
            verified=True,
        ),
        make_search_result(
            query=query,
            title="6204-2RS Bearing - Industrial Store",
            url="https://example.com/industrial/6204-2rs",
            snippet="Replacement bearing with 20mm inner diameter 47mm outer diameter 14mm width.",
            source_type_hint="industrial_marketplace",
            verified=True,
        ),
    ]


def _fake_mixed_material_search_web(query: str, provider: str | None = None, max_results: int = 5):
    return [
        make_search_result(
            query=query,
            title="HSR20 Linear Guide - In Stock",
            url="https://example.com/linear/hsr20",
            snippet="Price, stock, ships today.",
            source_type_hint="official_distributor",
            verified=True,
        ),
        make_search_result(
            query=query,
            title="6204-ZZ Ball Bearing - MISUMI Korea",
            url="https://example.com/misumi/6204-zz",
            snippet="20mm ID, 47mm OD, 14mm width, steel bearing.",
            source_type_hint="official_distributor",
            verified=True,
        ),
    ]


def _fake_extract_candidate_details(candidate, page_text, shortage_event, extraction_mode="none", model="gpt-4o-mini", api_key=None):
    return {
        "vendor_name": "MISUMI Korea",
        "price_krw": 15000,
        "raw_price_text": "15,000원",
        "listed_price": 15000,
        "listed_currency": "KRW",
        "lead_time_days": 1,
        "moq": None,
        "location": "Domestic",
        "source_type": "official_distributor",
        "price_listed": True,
        "stock_listed": True,
        "leadtime_listed": True,
        "spec_text": "6204-ZZ bearing 20mm ID 47mm OD 14mm width steel.",
        "spec_evidence": "Verified page table lists 20mm ID, 47mm OD, 14mm width, steel.",
    }


def _fake_many_verified_search_web(query: str, provider: str | None = None, max_results: int = 5):
    return [
        make_search_result(
            query=query,
            title=f"6204-ZZ Result {index}",
            url=f"https://example.com/product/{index}",
            snippet="20mm ID, 47mm OD, 14mm width, steel bearing.",
            source_type_hint="official_distributor",
            verified=True,
        )
        for index in range(1, 8)
    ]


if __name__ == "__main__":
    unittest.main()
