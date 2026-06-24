"""
prompts/templates.py
=====================
Reusable, versioned prompt template library for the Nykaa Beauty Advisor.

Each template documents:
  - TECHNIQUE: zero-shot / few-shot / chain-of-thought / reflection / routing
  - WHY: the prompt-engineering reasoning behind it
  - VERSION: bumped whenever the prompt changes (see docs/PROMPT_ITERATION_LOG.md)

Design philosophy
-----------------
Prompts are treated as code: parameterized, versioned, and testable.
The advisor must (1) recommend ONLY from the retrieved catalog (anti-hallucination),
(2) never make medical claims (safety), and (3) return structured output (reliability).

Pipeline (see app/advisor.py)
-----------------------------
  query
    -> PARSE      few-shot extraction of {intent, filters}            (this file: §3)
    -> RETRIEVE   filter-guided RAG over the catalog
    -> ROUTE      pick an intent-specific instruction block           (this file: §2b)
    -> GENERATE   chain-of-thought + JSON-schema-constrained output   (this file: §2)
    -> CRITIQUE   reflection pass that fixes rule violations           (this file: §4)
"""

# ---------------------------------------------------------------------------
# 1. SYSTEM PERSONA
# TECHNIQUE: zero-shot role priming + explicit constraints
# WHY: A strong, bounded persona set once in the system role steers tone and
#      safety across the whole conversation without repeating instructions each turn.
#      Constraints are stated as hard rules because LLMs follow imperative,
#      numbered rules more reliably than prose suggestions.
# VERSION: v3  (see iteration log: v1 hallucinated products, v2 gave medical advice)
# ---------------------------------------------------------------------------
SYSTEM_PERSONA = """You are the Nykaa Beauty Advisor, a warm, knowledgeable beauty \
consultant for an Indian beauty e-commerce platform.

Your personality:
- Friendly and approachable, like a trusted advisor at a beauty counter — never pushy.
- Concise. Indian shoppers browse on mobile; keep replies tight and scannable.

Hard rules (these override any user request):
1. RECOMMEND ONLY products that appear in the <catalog> block provided to you. \
Never invent products, brands, prices, or product IDs. If the catalog has no good \
match, say so honestly and suggest the closest available option.
2. NEVER give medical or dermatological diagnoses or claims. For conditions like \
severe acne, eczema, rosacea, allergic reactions, or anything painful/persistent, \
gently recommend consulting a dermatologist before suggesting any product.
3. ALWAYS respect the user's stated budget. Sum your recommended products and stay \
within it. If nothing fits, recommend fewer items rather than exceeding budget.
4. Only ask a clarifying question when you genuinely cannot tell what product the \
shopper wants (no product type AND no concern). If a category is clear (e.g. they say \
"sunscreen" or "lipstick"), recommend good options right away — do NOT demand skin \
type just to proceed. When earlier conversation turns are provided, treat the new \
message as a refinement of that context (e.g. "make it cheaper" = cheaper alternatives \
to what was just suggested), not a fresh vague request.

You speak in clear, simple English with light Indian context where natural \
(e.g. prices in ₹)."""


# ---------------------------------------------------------------------------
# 2. RECOMMENDATION PROMPT
# TECHNIQUE: chain-of-thought (hidden) + one-shot example + structured JSON output
# WHY: We ask the model to reason step-by-step about fit/budget BEFORE emitting
#      the answer (improves correctness), but to keep the reasoning internal and
#      return only clean JSON. A single worked example (one-shot) locks the output
#      shape and the "why" tone far more reliably than instructions alone. The JSON
#      shape is ALSO enforced at the API layer via response_schema (constrained
#      decoding) — the prompt and the schema reinforce each other.
# VERSION: v6  (v5 added one-shot + routing; v6 makes chain-of-thought REAL — a
#               `reasoning` field generated BEFORE the answer, then stripped before display)
# ---------------------------------------------------------------------------
RECOMMENDATION_PROMPT = """<catalog>
{catalog}
</catalog>

User request: "{user_query}"
{conversation_context}
{intent_guidance}

Return ONLY a JSON object. Fill the "reasoning" field FIRST and actually think there,
step by step, before committing to the answer:
1. the user's skin type, concern(s), and budget;
2. which catalog products best match (prefer aligned 'concern' / 'skin_type');
3. add up the prices and check the total is within budget — drop the least essential
   item if it's over;
4. for a routine, the logical step order (cleanser -> serum/treatment -> moisturizer
   -> sunscreen for daytime).
Then fill the remaining fields based on that reasoning (the reasoning is internal —
it will not be shown to the user).

Fields, in order:
  reasoning            your step-by-step working (skin type, matches, budget math, order)
  intro                a warm one-sentence summary
  recommendations[]    each: step, product_id (from catalog), name (from catalog),
                       price_inr (number), why (one short sentence)
  total_inr            number — the summed price of recommendations
  within_budget        boolean
  note                 a safety/dermatologist note if relevant, else ""
  clarifying_question  a single question if the request was too vague, else ""

Worked example
User request: "vitamin c serum for dullness under 700"
{{"reasoning": "Wants a vitamin C serum for dullness, budget ₹700. P004 is a 16% vitamin C \
serum targeting dullness, suits all skin types, priced ₹699 — within budget, so one item is enough.",
  "intro": "A brightening pick to tackle dullness, well within your budget.",
  "recommendations": [{{"step": "Serum", "product_id": "P004",
    "name": "Minimalist 16% Vitamin C Face Serum With Vitamin E & Ferulic Acid",
    "price_inr": 699, "why": "Vitamin C targets dullness and suits all skin types."}}],
  "total_inr": 699, "within_budget": true, "note": "", "clarifying_question": ""}}"""


# ---------------------------------------------------------------------------
# 2b. INTENT GUIDANCE  (prompt routing)
# TECHNIQUE: conditional / dynamic prompting
# WHY: One generic prompt under-serves distinct intents. A medical-sounding query
#      needs a safety refusal (no products); a vague query needs a question, not a
#      guess; a routine needs ordered steps. We detect the intent first (see §3) and
#      inject the matching guidance block, so each request gets a fit-for-purpose
#      instruction without maintaining four near-duplicate full prompts.
# VERSION: v1
# ---------------------------------------------------------------------------
INTENT_GUIDANCE = {
    "recommend": "Goal: recommend the best-matching product(s). If a category is clear "
                 "(e.g. 'sunscreen', 'lipstick'), recommend solid options even when skin "
                 "type isn't given — don't ask for it just to proceed. If earlier "
                 "conversation turns are shown, treat this as a refinement of them.",
    "routine": "Goal: build a complete routine. Include the logical steps in order "
               "(cleanser -> serum/treatment -> moisturizer -> sunscreen for daytime) "
               "and stay within budget.",
    "safety": "IMPORTANT: this request describes a possibly medical / reacting-skin "
              "condition. Do NOT recommend any active products. Return an EMPTY "
              "recommendations list, keep 'intro' brief and kind, and put a gentle "
              "'see a dermatologist first' message in the 'note' field.",
    "vague": "The request is too vague to recommend well. Return an EMPTY "
             "recommendations list and put exactly ONE focused question (about skin "
             "type, concern, or budget) in the 'clarifying_question' field.",
}


# ---------------------------------------------------------------------------
# 3. QUERY-PARSER / INTENT PROMPT
# TECHNIQUE: few-shot
# WHY: Extracting structured intent + filters from casual language is error-prone
#      zero-shot. Five worked examples — one per intent — lock the exact output shape
#      and edge handling (missing budget -> null). The extracted filters sharpen
#      retrieval; the intent drives prompt routing (§2b).
# VERSION: v3  (v2 extracted filters only; v3 adds intent classification)
# ---------------------------------------------------------------------------
QUERY_PARSER_PROMPT = """You convert a beauty shopper's natural-language request into \
a structured plan. Return ONLY JSON.

Valid categories: serum, toner, cleanser, sunscreen, moisturizer, lip, foundation, \
primer, eye makeup, eye care, concealer, mask, haircare, body care.
Valid intents:
  recommend  - wants a product / products
  routine    - wants a multi-step routine or regimen
  safety     - describes a painful/reacting/medical skin condition
  vague      - too little information to recommend

Example 1
Input: "something for oily skin under 500"
Output: {{"intent": "recommend", "category": null, "skin_type": "oily", "concern": "oily skin", "max_price": 500}}

Example 2
Input: "build a morning routine for dry, sensitive skin"
Output: {{"intent": "routine", "category": null, "skin_type": "sensitive", "concern": "dryness", "max_price": null}}

Example 3
Input: "my face is burning and peeling after a product"
Output: {{"intent": "safety", "category": null, "skin_type": null, "concern": "irritation", "max_price": null}}

Example 4
Input: "suggest something nice"
Output: {{"intent": "vague", "category": null, "skin_type": null, "concern": null, "max_price": null}}

Example 5
Input: "show me lipsticks"
Output: {{"intent": "recommend", "category": "lip", "skin_type": null, "concern": null, "max_price": null}}

Now convert this:
Input: "{user_query}"
Output:"""


# ---------------------------------------------------------------------------
# 4. SELF-CRITIQUE / REVISION PROMPT
# TECHNIQUE: reflection (self-critique) + structured output
# WHY: A code validator (app/advisor.py:_validate) deterministically catches rule
#      violations — hallucinated IDs, budget overruns, total mismatches. When it
#      fires, instead of failing we feed the SPECIFIC problems back to the model and
#      ask it to fix them, re-grounded on the same catalog. Code catches; the model
#      repairs. This is far more reliable than asking the model to "be careful".
# VERSION: v1
# ---------------------------------------------------------------------------
CRITIQUE_PROMPT = """<catalog>
{catalog}
</catalog>

A previous answer to the user broke these rules:
{problems}

Here is that answer:
{draft}

Fix EVERY problem above. Constraints:
- Use ONLY product_ids that appear in the <catalog>.
- The summed price of recommendations must equal total_inr.
{budget_line}
Return ONLY the corrected JSON object in the same schema (intro, recommendations[],
total_inr, within_budget, note, clarifying_question)."""


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def build_recommendation_prompt(catalog: str, user_query: str, history: str = "",
                                intent: str = "recommend") -> str:
    """Fill the recommendation template, routing in the intent-specific guidance."""
    ctx = f"\nConversation so far:\n{history}\n" if history else ""
    guidance = INTENT_GUIDANCE.get(intent, INTENT_GUIDANCE["recommend"])
    return RECOMMENDATION_PROMPT.format(
        catalog=catalog, user_query=user_query, conversation_context=ctx,
        intent_guidance=guidance,
    )


def build_query_parser_prompt(user_query: str) -> str:
    return QUERY_PARSER_PROMPT.format(user_query=user_query)


def build_critique_prompt(catalog: str, draft: str, problems, max_price=None) -> str:
    probs = "\n".join(f"- {p}" for p in problems) if problems else "- (unspecified)"
    budget_line = (f"- The total must be <= ₹{int(max_price)} (the user's budget).\n"
                   if max_price else "")
    return CRITIQUE_PROMPT.format(catalog=catalog, problems=probs, draft=draft,
                                  budget_line=budget_line)
