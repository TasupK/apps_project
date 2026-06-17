"""LLM-backed explanations for evaluation reports and user questions.

The rule engine remains the source of truth. These helpers only turn the
existing report fields into procurement-friendly Korean prose, with a
deterministic fallback for demos or offline runs.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from agents.web_research.config import DEFAULT_LLM_API_BASE, DEFAULT_OLLAMA_MODEL, DEFAULT_OPENAI_MODEL


def _llm_config() -> tuple[str, str, str]:
    token = os.environ.get("OPENAI_API_KEY") or os.environ.get("GPT_API_KEY")
    if token:
        return "https://api.openai.com/v1", token, os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    return (
        os.environ.get("OLLAMA_BASE_URL", DEFAULT_LLM_API_BASE).rstrip("/"),
        "ollama",
        os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
    )


def _llm_enabled(flag_name: str) -> bool:
    return os.environ.get(flag_name, "").strip().lower() in {"1", "true", "yes", "on"}


def _chat_completion(
    system_prompt: str,
    user_payload: dict,
    max_tokens: int = 500,
    prior_messages: list[dict] | None = None,
) -> str:
    base_url, token, model = _llm_config()
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if prior_messages:
        messages.extend(prior_messages)
    messages.append({"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)})
    request_body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    payload = json.dumps(request_body).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response_body = json.loads(response.read().decode("utf-8"))
    choices = response_body.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content")
        if content:
            return str(content).strip()
    for item in response_body.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return str(content["text"]).strip()
    raise RuntimeError("LLM response did not include text")


def _fallback_candidate_explanation(item: dict) -> str:
    candidate = item.get("candidate_material", {})
    decision = item.get("decision_context", {})
    scores = item.get("scores", {})
    spec = item.get("spec_analysis", {})
    source_notes = item.get("source_trust_notes", {})
    vendor_notes = item.get("vendor_trust_notes", {})

    decision_label = decision.get("decision", "review_required")
    reason = decision.get("recommendation_reason") or decision.get("rejection_reason") or "평가 근거가 부족합니다."
    risks = []
    risks.extend(source_notes.get("risk_factors", []) or [])
    risks.extend(vendor_notes.get("risk_factors", []) or [])
    if spec.get("highlighted_differences"):
        differences = [_format_difference(diff) for diff in spec["highlighted_differences"][:3]]
        risks.append("스펙 차이: " + "; ".join(differences))
    risk_text = " ".join(risks[:2]) if risks else "주요 리스크는 낮거나 리포트에 명시되지 않았습니다."
    return (
        f"{candidate.get('candidate_id', '후보')}는 {candidate.get('vendor_name', '공급사 미상')} 후보이며 "
        f"룰 기반 판단은 {decision_label}, 최종 점수는 {scores.get('final_score', '-')}점입니다. "
        f"{reason} {risk_text}"
    )


def _format_difference(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        field = value.get("field") or value.get("name") or "항목"
        target = value.get("target") or value.get("original") or value.get("expected")
        candidate = value.get("candidate") or value.get("actual")
        if target is not None or candidate is not None:
            return f"{field}: 원본 {target}, 후보 {candidate}"
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def explain_candidate_decision(item: dict) -> dict:
    """Return a Korean explanation object for one evaluated candidate."""
    fallback = _fallback_candidate_explanation(item)
    if not _llm_enabled("BUYBEE_ENABLE_LLM_EXPLANATIONS"):
        return {"provider": "rule_fallback", "text": fallback}

    payload = {
        "candidate_material": item.get("candidate_material", {}),
        "scores": item.get("scores", {}),
        "decision_context": item.get("decision_context", {}),
        "spec_analysis": item.get("spec_analysis", {}),
        "source_trust_notes": item.get("source_trust_notes", {}),
        "vendor_trust_notes": item.get("vendor_trust_notes", {}),
    }
    system_prompt = (
        "너는 산업재 구매 담당자를 돕는 설명 작성자다. "
        "룰 기반 decision, score, risk를 절대 바꾸지 말고 한국어로 2~3문장 설명만 작성한다. "
        "추측하지 말고 제공된 필드에 있는 근거만 사용한다."
    )
    try:
        return {"provider": "llm", "text": _chat_completion(system_prompt, payload, max_tokens=350)}
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, RuntimeError, json.JSONDecodeError):
        return {"provider": "rule_fallback", "text": fallback}


def _compact_report_context(
    event: dict,
    evaluation_report: dict | None,
    candidate_results: dict | None,
    po_row: dict | None,
) -> dict:
    items = []
    for item in (evaluation_report or {}).get("items", []):
        candidate = item.get("candidate_material", {})
        decision = item.get("decision_context", {})
        spec = item.get("spec_analysis", {})
        scores = item.get("scores", {})
        diffs = spec.get("highlighted_differences", [])
        items.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "vendor_name": candidate.get("vendor_name"),
                "price_krw": candidate.get("price_krw"),
                "lead_time_days": candidate.get("lead_time_days"),
                "source_type": candidate.get("source_type"),
                "source_url": candidate.get("source_url"),
                "decision": decision.get("decision"),
                "risk_level": decision.get("risk_level"),
                "reason": decision.get("recommendation_reason") or decision.get("rejection_reason"),
                "final_score": scores.get("final_score"),
                "compatibility_score": scores.get("compatibility_score"),
                "vendor_trust_score": scores.get("vendor_trust_score"),
                "source_trust_score": scores.get("source_trust_score"),
                "spec_differences": [_format_difference(d) for d in diffs[:5]],
                "explanation": item.get("llm_explanation", {}).get("text"),
            }
        )
    return {
        "shortage_event": {
            "material_id": event.get("material_id"),
            "material_name": event.get("material_name"),
            "current_stock": event.get("current_stock"),
            "safety_stock": event.get("safety_stock"),
            "shortage_qty": event.get("shortage_qty"),
            "technical_specification": event.get("technical_specification"),
        },
        "evaluation_summary": {
            "next_action": (evaluation_report or {}).get("next_action"),
            "top_candidate_id": (evaluation_report or {}).get("top_candidate_id"),
            "decision_counts": (evaluation_report or {}).get("decision_counts"),
        },
        "items": items,
        "query_used": (candidate_results or {}).get("query_used"),
        "po_row": po_row,
    }


def _rule_based_answer(
    prompt: str,
    context: dict,
    items: list[dict],
    top: dict,
    budget_limit_krw: int | None,
) -> str | None:
    """Return a rule-based answer string, or None if no rule matched."""
    lowered = prompt.strip().lower()

    if any(word in lowered for word in ["왜", "이유", "근거", "1순위", "추천"]):
        return (
            f"1순위는 **{top.get('vendor_name')} / {top.get('candidate_id')}**입니다. "
            f"판정은 `{top.get('decision')}`, 최종 점수는 {top.get('final_score')}점이고, "
            f"주요 근거는 {top.get('reason')}입니다."
        )

    if any(word in lowered for word in ["납기", "빠른", "빨리", "리드타임"]):
        ranked = sorted(
            items,
            key=lambda x: x.get("lead_time_days") if x.get("lead_time_days") is not None else 10**9,
        )
        fastest = ranked[0]
        return (
            f"납기가 가장 빠른 후보는 **{fastest.get('vendor_name')} / {fastest.get('candidate_id')}**이며 "
            f"납기는 {fastest.get('lead_time_days')}일입니다."
        )

    if any(word in lowered for word in ["가격", "금액", "단가", "저렴", "비싼", "비용"]):
        priced = [x for x in items if x.get("price_krw") not in {None, ""}]
        if not priced:
            return "가격이 확인된 후보가 없습니다. 가격 추출 또는 공급사 확인이 필요합니다."
        sorted_by_price = sorted(priced, key=lambda x: int(x.get("price_krw")))
        cheapest = sorted_by_price[0]
        most_expensive = sorted_by_price[-1]
        lines = [
            f"최저가: **{cheapest.get('vendor_name')} / {cheapest.get('candidate_id')}** — {int(cheapest.get('price_krw')):,}원",
            f"최고가: **{most_expensive.get('vendor_name')} / {most_expensive.get('candidate_id')}** — {int(most_expensive.get('price_krw')):,}원",
        ]
        if budget_limit_krw:
            over_budget = [x for x in priced if int(x.get("price_krw")) > budget_limit_krw]
            lines.append(f"예산({budget_limit_krw:,}원) 초과 후보: {len(over_budget)}개")
        return "\n".join(lines)

    if any(word in lowered for word in ["위험", "리스크", "risk", "위험도"]):
        risk_map: dict[str, list[str]] = {}
        for x in items:
            level = x.get("risk_level") or "unknown"
            risk_map.setdefault(level, []).append(
                f"{x.get('vendor_name')} / {x.get('candidate_id')}"
            )
        lines = [f"**{level}** ({len(cands)}개): {', '.join(cands)}" for level, cands in risk_map.items()]
        return "후보별 위험 수준:\n" + "\n".join(lines)

    if any(word in lowered for word in ["스펙", "spec", "사양", "차이", "비교", "다른점"]):
        has_diff = [x for x in items if x.get("spec_differences")]
        if not has_diff:
            return "스펙 차이 정보가 리포트에 포함되어 있지 않습니다."
        lines = []
        for x in has_diff[:3]:
            diffs_text = " / ".join(x["spec_differences"])
            lines.append(f"**{x.get('vendor_name')} / {x.get('candidate_id')}**: {diffs_text}")
        return "주요 스펙 차이:\n" + "\n".join(lines)

    if any(word in lowered for word in ["예산", "budget", "초과", "한도", "예산 초과"]):
        if not budget_limit_krw:
            return "예산 한도 정보가 설정되어 있지 않습니다."
        priced = [x for x in items if x.get("price_krw") not in {None, ""}]
        over = [x for x in priced if int(x.get("price_krw")) > budget_limit_krw]
        within = [x for x in priced if int(x.get("price_krw")) <= budget_limit_krw]
        return (
            f"예산 한도: **{budget_limit_krw:,}원**\n"
            f"한도 내 후보: {len(within)}개 / 초과 후보: {len(over)}개\n"
            + (
                "초과 후보: " + ", ".join(f"{x.get('vendor_name')}({int(x.get('price_krw')):,}원)" for x in over)
                if over else "모든 가격 확인 후보가 예산 내에 있습니다."
            )
        )

    if any(word in lowered for word in ["점수", "스코어", "score", "채점", "평점"]):
        lines = []
        for x in sorted(items, key=lambda x: x.get("final_score") or 0, reverse=True):
            lines.append(
                f"**{x.get('vendor_name')} / {x.get('candidate_id')}** — "
                f"최종 {x.get('final_score')}점 "
                f"(호환성 {x.get('compatibility_score')}, 공급사신뢰 {x.get('vendor_trust_score')}, 소스신뢰 {x.get('source_trust_score')})"
            )
        return "후보 점수 순위:\n" + "\n".join(lines)

    if any(word in lowered for word in ["소스", "출처", "url", "링크", "웹사이트", "사이트"]):
        lines = []
        for x in items:
            url = x.get("source_url") or "URL 없음"
            src = x.get("source_type") or "타입 미상"
            lines.append(f"**{x.get('vendor_name')} / {x.get('candidate_id')}** — [{src}] {url}")
        return "후보 소스 정보:\n" + "\n".join(lines)

    if any(word in lowered for word in ["전체", "요약", "모든", "목록", "리스트", "다 보여", "전부"]):
        lines = []
        for x in items:
            price_text = f"{int(x.get('price_krw')):,}원" if x.get("price_krw") not in {None, ""} else "가격 미상"
            lead_text = f"{x.get('lead_time_days')}일" if x.get("lead_time_days") is not None else "납기 미상"
            lines.append(
                f"- **{x.get('vendor_name')} / {x.get('candidate_id')}** "
                f"[{x.get('decision')}] 점수:{x.get('final_score')} "
                f"가격:{price_text} 납기:{lead_text} 위험:{x.get('risk_level')}"
            )
        return f"전체 후보 {len(items)}개 요약:\n" + "\n".join(lines)

    if any(word in lowered for word in ["몇", "개수", "수는", "총", "합계"]):
        counts = context["evaluation_summary"].get("decision_counts") or {}
        count_text = " / ".join(f"{k}: {v}개" for k, v in counts.items()) if counts else ""
        return (
            f"현재 평가된 후보는 총 **{len(items)}개**입니다."
            + (f" ({count_text})" if count_text else "")
        )

    return None


def answer_report_question(
    prompt: str,
    event: dict,
    evaluation_report: dict | None,
    candidate_results: dict | None,
    po_row: dict | None = None,
    chat_history: list[dict] | None = None,
    budget_limit_krw: int | None = None,
) -> str:
    """Answer a user's free-form question from report data, optionally using an LLM."""
    context = _compact_report_context(event, evaluation_report, candidate_results, po_row)
    items = context["items"]
    if not items:
        return "아직 평가 리포트가 없습니다. 먼저 대체 후보 검색과 평가를 실행해주세요."

    top_id = context["evaluation_summary"].get("top_candidate_id")
    top = next((x for x in items if x.get("candidate_id") == top_id), items[0])

    if not _llm_enabled("BUYBEE_ENABLE_LLM_CHAT"):
        rule_answer = _rule_based_answer(prompt, context, items, top, budget_limit_krw)
        if rule_answer:
            return rule_answer
        return (
            f"현재 리포트 기준 후보는 {len(items)}개이고, 다음 액션은 `{context['evaluation_summary'].get('next_action')}`입니다. "
            f"1순위 후보는 **{top.get('vendor_name')} / {top.get('candidate_id')}**입니다.\n"
            "더 구체적으로 물어보시려면: 납기, 가격, 위험, 스펙 차이, 점수, 소스, 전체 요약 등을 말씀해 주세요."
        )

    system_prompt = (
        "너는 BuyBee 조달 리포트 어시스턴트다. 제공된 JSON 리포트 안의 정보만 사용해 한국어로 짧게 답한다. "
        "모르면 모른다고 말하고, 후보 ID/공급사/점수/가격/납기 같은 근거를 함께 제시한다. "
        "승인이나 발주를 임의로 수행했다고 말하지 않는다."
    )
    prior_messages: list[dict] | None = None
    if chat_history:
        # Pass last 4 exchanges (up to 8 messages) — skip very long pipeline execution messages
        trimmed = [
            {"role": m["role"], "content": m["content"][:800]}
            for m in chat_history[-8:]
            if m.get("role") in {"user", "assistant"} and len(m.get("content", "")) < 2000
        ]
        prior_messages = trimmed or None

    try:
        return _chat_completion(
            system_prompt,
            {"question": prompt, "report_context": context},
            max_tokens=650,
            prior_messages=prior_messages,
        )
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, RuntimeError, json.JSONDecodeError):
        rule_answer = _rule_based_answer(prompt, context, items, top, budget_limit_krw)
        if rule_answer:
            return rule_answer
        return (
            f"현재 리포트 기준 후보는 {len(items)}개이고, 다음 액션은 `{context['evaluation_summary'].get('next_action')}`입니다. "
            f"1순위 후보는 **{top.get('vendor_name')} / {top.get('candidate_id')}**이며 주요 근거는 {top.get('reason')}입니다."
        )
