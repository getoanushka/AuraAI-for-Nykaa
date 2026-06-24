# Prompt Iteration Log

This log documents how each prompt evolved through observed failures and fixes. It
is the core artifact of this project: it shows prompt engineering as a systematic,
debuggable discipline rather than trial-and-error luck.

Format per entry: **what I observed → why it happened → what I changed → result.**

---

## System Persona Prompt

### v1 → v2  (hallucinated products)
- **Observed:** With a friendly persona but no grounding rule, the model confidently
  recommended products that don't exist in the catalog (e.g. "Nykaa Naturals Tea Tree
  Toner") with invented prices.
- **Why:** The prompt described a helpful advisor but never constrained the model to
  the catalog. LLMs default to plausible-sounding generation.
- **Change:** Added Hard Rule #1 — recommend ONLY from the `<catalog>` block; never
  invent products, brands, prices, or IDs.
- **Result:** Hallucinated products dropped sharply. (A code-level validator was added
  later as defense-in-depth, since prompt rules alone are not a guarantee.)

### v2 → v3  (gave medical advice)
- **Observed:** For "I have painful cystic acne," the model recommended specific
  actives and implied they would treat the condition — a medical claim and a real
  liability for a retail brand.
- **Why:** No safety boundary in the persona.
- **Change:** Added Hard Rule #2 — no medical/dermatological claims; refer serious or
  painful conditions to a dermatologist before any product suggestion.
- **Result:** Medical-sounding queries now trigger a dermatologist referral in the
  `note` field. (Verified by eval cases SAF-01, SAF-02.)

---

## Recommendation Prompt

### v1 → v2  (rambling prose, unparseable)
- **Observed:** Output was a friendly paragraph. Impossible to render in a UI or
  validate programmatically.
- **Why:** No output-format instruction.
- **Change:** Specified an exact JSON schema and "return ONLY valid JSON, no markdown."
- **Result:** Structured, parseable output.

### v2 → v3  (ignored budget)
- **Observed:** For "under 2000," recommended items summing to ₹2,400.
- **Why:** The model picked the "best" products without doing arithmetic on price.
- **Change:** Added an explicit chain-of-thought instruction to *add up prices and
  drop the least essential item if over budget* — reasoning performed before output.
- **Result:** Budget adherence improved markedly. A code validator now also re-checks
  the total (consistency check in `_validate`).

### v3 → v4  (occasional ```json fences despite instructions)
- **Observed:** ~10% of responses wrapped JSON in markdown code fences, breaking naive
  `json.loads`.
- **Why:** Strong model habit; a single instruction doesn't fully suppress it.
- **Change:** Two-pronged — kept the "no markdown" instruction AND wrote a tolerant
  `_extract_json` that strips fences and grabs the outermost `{...}`.
- **Result:** Parsing reliability effectively 100%. Lesson: pair prompt instructions
  with defensive parsing; don't rely on the prompt alone for machine-critical format.

### v4 → v5  (inconsistent "why" tone + format drift; parsing still probabilistic)
- **Observed:** Zero-shot CoT gave correct data but the `why` lines drifted in tone
  and length, and format compliance was still ~90% (handled by defensive parsing).
- **Why:** Instructions describe the shape; they don't *demonstrate* it. And the JSON
  contract lived only in the prompt — nothing enforced it.
- **Change:** (a) Added a **one-shot worked example** to lock the output shape and the
  `why` voice; (b) moved to **native schema-constrained output** (`response_schema` in
  `app/advisor.py`) so the API itself guarantees valid JSON — the regex parser is now a
  fallback, not the primary path.
- **Result:** Format compliance effectively 100% at the API layer; steadier tone.
  Lesson: constrain output at the decoding layer when the platform supports it, and
  show — don't just tell — the format.

### v5 → v6  (the "chain-of-thought" was nominal, not real)
- **Observed:** The prompt said "think step by step" but also "do NOT show your reasoning,
  return ONLY JSON" — and `thinking_budget=0` disabled native thinking. So the model had
  **no space to actually reason**; it emitted final JSON directly. Budget/ordering
  correctness was really being caught by the code validator, not by reasoning.
- **Why:** You can't claim chain-of-thought while forbidding the model any place to do it.
  Reasoning has to live *somewhere* in the generation.
- **Change:** Added a **`reasoning` field as the FIRST property** of the response schema.
  Because generation is autoregressive, the model writes its step-by-step working
  (skin type → matches → budget math → order) **before** the recommendations, so the
  answer is genuinely conditioned on it. The field is then **stripped in code** before
  the response reaches the UI (kept as metadata for transparency).
- **Result:** Real, inspectable chain-of-thought with clean user-facing output. Lesson:
  with structured output, *field order is a reasoning lever* — put the thinking first.

---

## Query-Parser / Intent Prompt

### v1 → v2  (wrong shape on missing fields)
- **Observed:** Zero-shot, when budget was absent, the model sometimes omitted the
  `max_price` key entirely or set it to the string "none".
- **Why:** No example pinned down the missing-value convention.
- **Change:** Switched to **few-shot** with two examples, one of which has a null
  budget, fixing the convention to JSON `null`.
- **Result:** Consistent output shape; downstream filtering no longer crashes.

### v2 → v3  (parser existed but did nothing; one prompt served every intent)
- **Observed:** The few-shot parser was defined but never called — the pipeline ran one
  recommendation prompt for *every* request, so vague and medical-sounding queries were
  handled with the same instructions as a normal product search.
- **Why:** No routing layer. Intent was never determined, so the prompt couldn't adapt.
- **Change:** Extended the parser to also classify **intent** (recommend / routine /
  safety / vague) via a 5th few-shot example per intent, then **wired it into the
  pipeline**: the extracted filters now sharpen retrieval, and the intent selects an
  intent-specific guidance block (`INTENT_GUIDANCE`) injected into the generation prompt.
- **Result:** Safety queries reliably return a dermatologist note with no products;
  vague queries return a single clarifying question; routines get ordered steps.

---

## Self-Critique Prompt (new)

### v0 → v1  (validator caught violations but the request just failed)
- **Observed:** When `_validate` flagged a hallucinated ID or a budget overrun, the user
  got an error/invalid result rather than a good answer.
- **Why:** Validation was a dead end — it detected problems but couldn't fix them.
- **Change:** Added a **reflection pass**: the specific validator problems are fed back to
  the model with the catalog, and it is asked to repair them. The revision is only
  accepted if it actually reduces the problem count.
- **Result:** "Code catches, model repairs" — most rule violations are silently corrected
  before the user ever sees them, while the deterministic validator remains the backstop.

---

## Cross-cutting lessons
1. **Ground, then verify.** Prompt rules reduce hallucination; code validation
   catches the residual. Use both.
2. **Make reasoning happen before output.** Chain-of-thought on budget math fixed a
   problem that no amount of "please respect budget" phrasing solved.
3. **Few-shot beats zero-shot for fixed output shapes**, especially around edge cases
   like missing values.
4. **Never trust a model for machine-critical formatting.** Defensive parsing is
   cheap insurance — but if the platform offers schema-constrained decoding, use it
   as the primary guarantee and keep parsing as the fallback.
5. **Route by intent.** One prompt can't serve a product search, a routine, a vague
   ask, and a medical concern equally well. Classify first, then inject fit-for-purpose
   guidance — far cleaner than one bloated prompt with every caveat.
6. **Let the model repair itself.** A deterministic validator that *detects* problems
   becomes far more useful when paired with a reflection pass that *fixes* them, with
   the validator as the final backstop.
