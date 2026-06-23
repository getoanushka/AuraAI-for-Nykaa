"""
app/advisor.py
==============
The Beauty Advisor agent: orchestrates the RAG + prompting workflow.

Pipeline (each step is a prompt-engineering technique):
  user_query
    -> PARSE      few-shot extraction of {intent, filters}        (templates §3)
    -> RETRIEVE   filter-guided RAG over the catalog              (app/retrieval.py)
    -> ROUTE      pick an intent-specific instruction block       (templates §2b)
    -> GENERATE   chain-of-thought + JSON-schema output           (templates §2)
    -> VALIDATE   anti-hallucination + budget checks in CODE
    -> CRITIQUE   reflection pass that repairs rule violations     (templates §4)

Why two layers of safety: even a well-grounded LLM can invent an ID or bust a
budget. We catch it deterministically in code (_validate) and then let the model
*repair* its own answer (self-critique) — defense in depth for production e-commerce.

Structured output: the model is constrained to a JSON schema at the API layer
(response_schema), so we get valid JSON without the old regex-extraction hack.
"""

import json
import os
import re

from app.retrieval import retrieve, catalog_block, load_catalog
from prompts.templates import (
    SYSTEM_PERSONA,
    build_recommendation_prompt,
    build_query_parser_prompt,
    build_critique_prompt,
)

MODEL = "gemini-2.5-flash-lite"  # higher free-tier quota than -flash; swap to
#                                  gemini-2.5-flash / -pro for higher quality

# The few-shot LLM parser is an extra Gemini call per query. On the tight free-tier
# quota we default to the fast rule-based router and only use the LLM parser when
# USE_LLM_PARSER=1 is set. (The parser prompt is still part of the library / docs.)
USE_LLM_PARSER = bool(os.environ.get("USE_LLM_PARSER"))

PARSER_SYSTEM = ("You are a precise parser that turns beauty-shopping requests into "
                 "structured JSON. Follow the examples exactly.")


# --------------------------------------------------------------------------
# Output schemas (enforced by Gemini via response_schema / constrained decoding).
# pydantic ships with the google-genai SDK, so no extra dependency.
# --------------------------------------------------------------------------
try:
    from pydantic import BaseModel
    from typing import Literal, Optional

    class Recommendation(BaseModel):
        step: str
        product_id: str
        name: str
        price_inr: float
        why: str

    class Answer(BaseModel):
        intro: str
        recommendations: list[Recommendation]
        total_inr: float
        within_budget: bool
        note: str
        clarifying_question: str

    class ParsedQuery(BaseModel):
        intent: Literal["recommend", "routine", "safety", "vague"]
        category: Optional[str] = None
        skin_type: Optional[str] = None
        concern: Optional[str] = None
        max_price: Optional[float] = None

except ImportError:  # pragma: no cover - pydantic always present with the SDK
    Recommendation = Answer = ParsedQuery = None


def _get_client():
    """Lazy import so the repo loads even without the SDK/key present."""
    try:
        from google import genai
    except ImportError:
        return None
    if not os.environ.get("GEMINI_API_KEY"):
        return None
    return genai.Client()  # reads GEMINI_API_KEY from the environment


def _generate(client, prompt, system_instruction, schema):
    """
    One constrained Gemini call. `schema` (a pydantic model) forces valid JSON.
    Retries transient 429/5xx with backoff. Returns a parsed dict.
    """
    import time

    from google.genai import types
    from google.genai import errors as genai_errors

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        max_output_tokens=1024,
        temperature=0,  # determinism so the consistency eval is meaningful
        # gemini-2.5-* "thinks" by default, which can silently eat the output
        # token budget; our chain-of-thought is prompt-level, so turn it off.
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        response_mime_type="application/json",
        response_schema=schema,
    )
    last_err = None
    for attempt in range(4):
        try:
            resp = client.models.generate_content(
                model=MODEL, contents=prompt, config=config
            )
            raw = resp.text or "{}"
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return _extract_json(raw)  # belt-and-suspenders fallback
        except genai_errors.APIError as e:
            last_err = e
            if e.code in (429, 500, 503) and attempt < 3:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s
                continue
            raise
    raise last_err


def _extract_json(text):
    """Fallback JSON extraction if a response ever slips past the schema."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in model output: {text[:200]}")
    return json.loads(text[start : end + 1])


def _validate(parsed, retrieved_rows, max_price=None):
    """Anti-hallucination + budget/consistency checks. Returns (ok, problems)."""
    problems = []
    all_ids = {r["product_id"] for r in load_catalog()}

    recs = parsed.get("recommendations", [])
    running = 0.0
    for rec in recs:
        pid = rec.get("product_id")
        if pid not in all_ids:
            problems.append(f"hallucinated product_id: {pid}")
        running += float(rec.get("price_inr", 0) or 0)

    stated = parsed.get("total_inr")
    if stated is not None and abs(float(stated) - running) > 1:
        problems.append(f"total mismatch: stated {stated}, summed {running}")

    if max_price and running > float(max_price) + 1:
        problems.append(f"over budget: summed {running} > {max_price}")

    return (len(problems) == 0), problems


ROUTINE_CATS = ["cleanser", "serum", "toner", "moisturizer", "sunscreen", "eye care"]


def _diversify_for_routine(rows, per_cat=2):
    """Spread retrieved rows across routine categories so a full routine
    (cleanser -> serum -> moisturizer -> sunscreen) can be built, instead of the
    model only seeing e.g. three cleansers. Falls back to the original rows if
    there isn't enough category variety."""
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    picked = []
    for cat in ROUTINE_CATS:
        picked += by_cat.get(cat, [])[:per_cat]
    if len({r["category"] for r in picked}) < 3:
        return rows
    return picked


def _rule_intent(query):
    """Lightweight intent detection used in MOCK mode (no API key)."""
    q = query.lower()
    if re.search(r"cystic|bleeding|painful|burning|rash|infection|eczema|rosacea|"
                 r"allergic|peeling|irritat", q):
        return "safety"
    if re.search(r"routine|regimen", q):
        return "routine"
    # vague: very short and no category/concern/skin-type signal
    if len(re.findall(r"[a-z]+", q)) <= 3 and not re.search(
            r"serum|sunscreen|cleanser|lip|toner|moistur|foundation|oily|dry|acne", q):
        return "vague"
    return "recommend"


def advise(user_query, history="", max_price=None):
    """
    Main entry point. Returns the parsed answer plus metadata (intent, retrieval
    backend, validation result, whether a self-critique pass ran). Falls back to a
    deterministic mock if no API key is configured, so the pipeline is testable offline.
    """
    client = _get_client()

    # ---- MOCK MODE (no key): rule-based intent + deterministic answer ----
    if client is None:
        intent = _rule_intent(user_query)
        if history and intent == "vague":  # a follow-up in context isn't vague
            intent = "recommend"
        rows, backend = retrieve((user_query + " " + history).strip(),
                                 k=(24 if intent == "routine" else 8), max_price=max_price)
        if intent == "routine":
            rows = _diversify_for_routine(rows)
        return {
            "answer": _mock_answer(rows, user_query, max_price, intent),
            "retrieval_backend": backend,
            "valid": True,
            "problems": [],
            "intent": intent,
            "self_critiqued": False,
            "note_to_dev": "No GEMINI_API_KEY set — returned a deterministic mock. "
            "Set the key to run the full Gemini prompt pipeline.",
        }

    # ---- 1. PARSE: intent + filters ----
    # Default: fast rule-based router (no extra Gemini call). Optional: the few-shot
    # LLM parser when USE_LLM_PARSER=1 (and not an obvious safety query, which only
    # needs a refusal). Fewer calls = the free-tier quota stretches much further.
    if USE_LLM_PARSER and _rule_intent(user_query) != "safety":
        try:
            parsed_q = _generate(client, build_query_parser_prompt(user_query),
                                 PARSER_SYSTEM, ParsedQuery)
        except Exception:
            parsed_q = {"intent": _rule_intent(user_query)}  # fall back to rules
    else:
        parsed_q = {"intent": _rule_intent(user_query)}
    intent = parsed_q.get("intent", "recommend")
    # A follow-up inside an ongoing conversation ("make it cheaper", "add one more")
    # is a refinement, not a cold vague ask — don't route it to a clarifying question.
    if history and intent == "vague":
        intent = "recommend"
    # explicit caller budget (e.g. UI slider) wins; else use the parsed budget
    eff_price = max_price if max_price is not None else parsed_q.get("max_price")

    # ---- 2. RETRIEVE: enrich the query with parsed filters + conversation context ----
    # Including `history` keeps follow-ups on-topic: "make it cheaper" alone retrieves
    # nothing useful, but with the prior turn / current bag ("...Sunscreen...") in the
    # query, retrieval returns sunscreens — not whatever is cheapest in the catalog.
    enriched = " ".join(filter(None, [
        parsed_q.get("concern"), parsed_q.get("skin_type"),
        parsed_q.get("category"), user_query, history,
    ]))
    rows, backend = retrieve(enriched, k=(24 if intent == "routine" else 8), max_price=eff_price)
    if intent == "routine":
        rows = _diversify_for_routine(rows)
    catalog = catalog_block(rows)

    # ---- 3 + 4. ROUTE to an intent-specific prompt, then GENERATE (JSON schema) ----
    prompt = build_recommendation_prompt(catalog, user_query, history, intent)
    try:
        answer = _generate(client, prompt, SYSTEM_PERSONA, Answer)
    except (ValueError, json.JSONDecodeError) as e:
        return {"answer": None, "error": str(e), "retrieval_backend": backend,
                "valid": False, "intent": intent}
    except Exception as e:
        return {"answer": None, "error": f"Gemini error: {e}",
                "retrieval_backend": backend, "valid": False, "intent": intent}

    # ---- 5. VALIDATE in code; ---- 6. SELF-CRITIQUE & repair if rules were broken ----
    ok, problems = _validate(answer, rows, eff_price)
    self_critiqued = False
    if not ok:
        try:
            revised = _generate(
                client,
                build_critique_prompt(catalog, json.dumps(answer), problems, eff_price),
                SYSTEM_PERSONA, Answer,
            )
            self_critiqued = True
            ok2, problems2 = _validate(revised, rows, eff_price)
            if ok2 or len(problems2) < len(problems):  # accept only if it helped
                answer, ok, problems = revised, ok2, problems2
        except Exception:
            pass  # keep the original answer; code-level problems are still reported

    return {
        "answer": answer,
        "retrieval_backend": backend,
        "valid": ok,
        "problems": problems,
        "intent": intent,
        "self_critiqued": self_critiqued,
    }


def _mock_answer(rows, user_query, max_price=None, intent="recommend"):
    """Deterministic offline stand-in that honours the detected intent."""
    if intent == "safety":
        return {
            "intro": "I want to make sure you're looked after here.",
            "recommendations": [], "total_inr": 0, "within_budget": True,
            "note": "That sounds like something a dermatologist should check first. "
                    "Once it's cleared, I'd be happy to suggest gentle options.",
            "clarifying_question": "",
        }
    if intent == "vague":
        return {
            "intro": "Happy to help — just need a little more to go on!",
            "recommendations": [], "total_inr": 0, "within_budget": True, "note": "",
            "clarifying_question": "What's your skin type and which concern should we "
                                   "tackle first (e.g. oily, dryness, acne, dullness)?",
        }

    recs, total = [], 0.0
    seen_cats = set()
    limit = 4 if intent == "routine" else 3
    for r in rows:
        # for a routine, give one product per step (cleanser/serum/moisturizer/sunscreen)
        if intent == "routine" and r["category"] in seen_cats:
            continue
        price = float(r["price_inr"])
        if max_price and total + price > max_price:
            continue
        recs.append({
            "step": r["category"].title(),
            "product_id": r["product_id"],
            "name": r["name"],
            "price_inr": price,
            "why": f"Matches your interest in {r['concern']}.",
        })
        seen_cats.add(r["category"])
        total += price
        if len(recs) >= limit:
            break
    return {
        "intro": "Here's a quick routine based on what you described (mock output).",
        "recommendations": recs,
        "total_inr": total,
        "within_budget": (max_price is None) or (total <= max_price),
        "note": "",
        "clarifying_question": "",
    }
