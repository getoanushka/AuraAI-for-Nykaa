"""
test_pipeline.py
================
A guided tour of the prompt-engineering pipeline. Run it to *see* the four upgrades:

  1. Few-shot parser  -> each query gets classified into an INTENT
  2. Intent routing    -> safety / vague / routine / recommend behave differently
  3. JSON-schema output -> every answer is valid structured JSON (valid=True)
  4. Self-critique      -> rule violations get repaired (self_critiqued=True)

Run:
    venv/bin/python test_pipeline.py          # MOCK if no key, LIVE with GEMINI_API_KEY
"""

import os
from app.advisor import advise

LIVE = bool(os.environ.get("GEMINI_API_KEY"))

# (query, budget, what to look for)
CASES = [
    ("I have painful cystic acne that's bleeding", None,
     "SAFETY: expect 0 products + a dermatologist note (no actives pushed)"),
    ("suggest something nice", None,
     "VAGUE: expect 0 products + ONE clarifying question"),
    ("show me lipsticks", None,
     "RECOMMEND: expect lip products (this was the bug that returned serums)"),
    ("build a daytime routine for oily, acne-prone skin under 1500", 1500,
     "ROUTINE: expect ordered steps, total <= 1500"),
    ("cheapest sunscreen for oily skin", None,
     "RECOMMEND: expect a sunscreen, grounded to a real catalog id"),
]


def show(query, budget, hint):
    print("\n" + "=" * 78)
    print(f"QUERY : {query}   (budget: {budget})")
    print(f"EXPECT: {hint}")
    print("-" * 78)
    res = advise(query, max_price=budget)
    ans = res.get("answer")
    if not ans:
        print("  ERROR:", res.get("error"))
        return
    # the pipeline metadata — the interesting part
    print(f"  intent          = {res.get('intent')!r}        <- step 1: few-shot parser + routing")
    print(f"  retrieval       = {res.get('retrieval_backend')}")
    print(f"  valid (schema+rules) = {res.get('valid')}        <- steps 3 & 5: JSON schema + validator")
    print(f"  self_critiqued  = {res.get('self_critiqued')}        <- step 6: reflection repair pass")
    if res.get("problems"):
        print(f"  problems        = {res['problems']}")
    print(f"  intro           = {ans.get('intro')}")
    for r in ans.get("recommendations", []):
        print(f"    - [{r['product_id']}] {r['name'][:46]:46}  ₹{int(r['price_inr'])}  ({r['step']})")
    print(f"  total_inr       = {ans.get('total_inr')}  within_budget={ans.get('within_budget')}")
    if ans.get("note"):
        print(f"  note            = {ans['note']}")
    if ans.get("clarifying_question"):
        print(f"  clarifying_q    = {ans['clarifying_question']}")


if __name__ == "__main__":
    print("=" * 78)
    print(f"BEAUTY ADVISOR — PIPELINE TEST    (mode: {'LIVE (Gemini)' if LIVE else 'MOCK'})")
    if not LIVE:
        print("Set GEMINI_API_KEY to run the real Gemini pipeline (parser + critique calls).")
    print("=" * 78)
    for q, b, hint in CASES:
        show(q, b, hint)
    print("\nDone. Key things to verify:")
    print("  • intent matches each query type (safety/vague/routine/recommend)")
    print("  • 'show me lipsticks' returns LIP products, not serums")
    print("  • every answer has valid=True (schema-constrained JSON)")
    print("  • product_ids are real catalog ids (P0xx); totals respect budget")
