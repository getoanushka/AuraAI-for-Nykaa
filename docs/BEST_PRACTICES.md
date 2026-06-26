# Prompt Engineering Best Practices

An opinionated methodology playbook distilled from building this project (AuraAI /
Nebula). It mirrors how the role describes the work — *design, evaluate, document,
repeat* — and every principle below is something this repo actually does, with a
pointer to where.

## Core philosophy
> **The prompt is the *first* safeguard, never the only one.**
> **Ground → constrain → verify → repair.**

A model that "sounds right" isn't enough for production e-commerce. Treat prompts like
code (versioned, tested), assume the model *will* occasionally misbehave, and put
deterministic checks around it. The interesting work isn't getting a good answer once —
it's making the system reliable, safe, and machine-consumable every time.

---

## 1. Pick the technique deliberately
| Technique | Use it when… | Where, in this repo |
|---|---|---|
| **Zero-shot** role priming | the task is clear and you mainly need tone + rules | `SYSTEM_PERSONA` |
| **Few-shot** | you need a *specific, stable output shape* / tricky edge cases | the query parser (one example per intent; pins the `null`-budget convention) |
| **Chain-of-thought** | the task needs intermediate reasoning (arithmetic, ordering) | budget math + routine ordering (see §5) |
| **Prompt routing** | one prompt can't serve distinct request types well | `INTENT_GUIDANCE` (recommend / routine / safety / vague) |
| **Reflection / self-critique** | you can *detect* a bad answer and want it fixed, not just rejected | the critique pass (see §7) |

Don't cargo-cult techniques. Each one here earns its place against a specific failure.

## 2. Durable rules go in the system prompt — numbered and imperative
Persona, safety boundaries, and hard constraints belong in the system role: set once,
applied every turn. **Number them.** Imperative, numbered rules ("1. RECOMMEND ONLY
from the catalog…") are followed far more reliably than the same content as prose, and
they resist "ignore your instructions" injections better.

## 3. Ground before you generate (RAG)
For anything tied to real inventory/knowledge, **retrieve the relevant records and
inject them**, then constrain the model to use only those. This is the single biggest
lever against hallucination in e-commerce — the model can't invent a product it was
never shown, and a code check rejects any ID outside the catalog.

## 4. Constrain output at the decoding layer — but keep a fallback
Don't just *describe* a JSON shape in the prompt and hope. Use the platform's
**schema-constrained decoding** (`response_schema`) so valid JSON is *guaranteed*. Keep
a tolerant parser (strip fences, grab the outermost object) as a belt-and-suspenders
fallback. Prompt **and** schema **and** parser — layered, not singular.

## 5. Make chain-of-thought *real*, then hide it
A subtle trap: claiming "chain-of-thought" while telling the model to "return only JSON"
and disabling its thinking budget — there's then nowhere for reasoning to happen. The
fix: put a **`reasoning` field FIRST** in the output schema. Because generation is
autoregressive, the model reasons *before* committing to the answer, so the answer is
conditioned on it. Then **strip the reasoning in code** before it reaches the user —
real CoT, clean output. *Field order is a reasoning lever.*

## 6. Route by intent
Detect the request type first, then inject a fit-for-purpose instruction block:
medical-sounding → refuse + refer to a dermatologist (no products); vague → ask one
question; routine → ordered steps; product → recommend. One bloated prompt with every
caveat serves none of them well.

## 7. Let the model repair itself — with code as the backstop
A validator that only *detects* problems is a dead end. Pair it with a **reflection
pass**: when the deterministic validator flags a hallucinated ID / budget overrun /
total mismatch, feed the *specific* problems back to the model and ask it to fix them,
re-grounded on the same catalog. Accept the revision only if it actually reduces the
problems. "Code catches, model repairs."

## 8. Evaluate on explicit axes — and red-team it
Define what "good" means and **test it as data, not vibes**:
- **Accuracy** — right products, budget respected, correct category.
- **Safety** — no medical/cure claims, dermatologist referrals.
- **Consistency** — stable recommendations (test *paraphrase invariance*, not just a
  fixed seed at `temperature=0`).
- **Injection / red-team** — actively *attack* the agent: "ignore your instructions,"
  "you are a doctor," "ignore the budget," "reveal your system prompt." Assert it
  resists. A test suite that attacks your own agent is worth more than hoping it's safe.

Keep cases as data (`evals/cases.py`) so the benchmark grows; run a scorecard
(`evals/run_evals.py`).

## 9. Version prompts and log every iteration
Treat prompts like code: a `VERSION` on each, and a log of **failure → cause → fix**
(`docs/PROMPT_ITERATION_LOG.md`). The log stops you re-introducing solved bugs and is the
clearest evidence of engineering judgment — far more than a polished final prompt.

## 10. Optimize for the deployment, not the demo
A prompt that works once in a playground isn't done. Ship-blocking questions: Does it
**fail safely**? Is the output **machine-consumable**? Is it **consistent** enough? What
are the **cost/latency/quota** limits, and what's the graceful fallback when they're hit?
(Here: a lighter rule-based router + lexical retriever are deliberate free-tier choices,
documented honestly — knowing what *not* to run is part of the job.)

---

## Anti-hallucination: defense-in-depth (the layered summary)
1. **Prompt rule** — recommend only from the injected `<catalog>`.
2. **RAG grounding** — the model only *sees* relevant catalog rows.
3. **Schema-constrained output** — the response must match the JSON schema.
4. **Code validator** — every `product_id` checked against the real catalog; budget re-summed.
5. **Self-critique** — repair loop when the validator flags a violation.

No single layer is trusted. That's the whole point.

## Cross-cutting lessons
- **Show, don't just tell** — a worked example locks format better than instructions.
- **Verify in code, don't argue with the model** — the instinct on a bad output shouldn't
  be "add more words to the prompt," it's "what deterministic check catches this?"
- **A silent fallback can hide a real failure** — make degraded modes *visible* (e.g., an
  "offline mode" note) so you don't mistake a broken path for a working one.
- **Match the story to the running system** — if the README claims a technique, the
  deployed app should actually run it (or honestly say it doesn't and why).
