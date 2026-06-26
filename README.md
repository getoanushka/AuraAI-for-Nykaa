#  AuraAI — Nykaa Beauty Advisor

 Live demo: https://auraai-for-nykaa.onrender.com
*(Hosted on Render's free tier — the first load may take ~30–50s while the instance wakes up.)*

A **Google Gemini–powered**, RAG-grounded conversational beauty advisor. It recommends
products from a grounded catalog, respects the shopper's budget, refuses to give medical
advice, and returns clean structured output — wrapped in a **versioned prompt library**,
an **evaluation harness**, and a **prompt iteration log**.

It ships with **AuraAI**, a single-file storefront whose floating advisor **Nebula** takes
real cart actions and links straight out to Nykaa.com.

> Powered by **Google Gemini** (`gemini-2.5-flash-lite` by default). Set a
> `GEMINI_API_KEY` to run the real model; without one it falls back to a deterministic
> mock so the project still runs end-to-end.

---

## What it demonstrates

- **Prompt engineering as a discipline** — a versioned, annotated prompt library
  (`prompts/templates.py`) using **zero-shot** persona priming, **few-shot** intent
  parsing, real **chain-of-thought** (a reasoning field generated before the answer, then
  stripped), **prompt routing**, and a **self-critique** reflection pass.
- **A real agent pipeline** (`app/advisor.py`): parse → retrieve → route → generate →
  validate → self-correct.
- **RAG** (`app/retrieval.py`): the **lexical retriever** (dependency-free, what runs and is
  tested) plus an *implemented* semantic vector path (Chroma + sentence-transformers) as a
  drop-in upgrade for a larger instance (see the config note below).
- **Structured output**: Gemini is constrained to a JSON schema (`response_schema`), so
  the model is *forced* to emit valid JSON — not coaxed by instructions alone.
- **Evaluation**: an accuracy / safety / consistency scorecard (`evals/`).
- **An agentic storefront** (`storefront.html`): natural-language cart actions, real
  product images, and checkout that opens the bagged items on Nykaa.
- **Cycle-aware skincare** — a Clue-style menstrual-cycle tracker that reads your current
  phase and builds a routine matched to how your skin behaves in it.

## The prompt pipeline

```
user query
  → PARSE      intent + filters         (few-shot LLM parser; rule-based fallback)
  → RETRIEVE   grounded catalog rows     (lexical by default; vector RAG with optional deps)
  → ROUTE      intent-specific prompt    (recommend / routine / safety / vague)
  → GENERATE   Gemini → JSON schema      (constrained decoding; reasoning-first chain-of-thought)
  → VALIDATE   anti-hallucination + budget checks, in code
  → CRITIQUE   feed problems back to the model to repair, if any
  → render     demo.py / Streamlit / the AuraAI storefront
```

### What runs where (honest config note)
The same code supports a full and a lightweight path; the live free-tier deploy runs the
lightweight one **by design**, not by omission:
- **Intent parser:** the few-shot LLM parser is **on by default**; set `USE_LLM_PARSER=0` to
  use the rule-based router (one fewer Gemini call) when the free-tier quota is tight. The
  rule-based router is also the automatic fallback if a parser call fails.
- **Retrieval:** a vector-RAG path (Chroma + sentence-transformers embeddings) is
  *implemented* in `app/retrieval.py`, but the **dependency-free lexical retriever is what
  actually runs and is tested** everywhere — including the free-tier deploy (Chroma + PyTorch
  don't fit Render's 512 MB). The vector path is a drop-in upgrade (same interface) for a
  larger instance, not something this deployment exercises. A deliberate cost/infra tradeoff.
- **Chain-of-thought:** real — the model fills a `reasoning` field *before* the answer
  (autoregressive conditioning), which is then stripped before display.

## Defense-in-depth against hallucination
1. **Prompt rule:** recommend only from the injected `<catalog>`.
2. **RAG grounding:** only relevant catalog rows are shown to the model.
3. **Schema-constrained output:** the response must match the JSON schema.
4. **Code validator:** every returned `product_id` is checked against the real catalog
   and the budget total is re-summed.
5. **Self-critique:** when the validator flags a problem, the model is asked to fix it.

The prompt is never the only safeguard.

## The AuraAI storefront
`storefront.html` is a self-contained mini "Nykaa" storefront with a draggable floating
advisor, **Nebula**. Type what you want and it fills your bag, builds routines, guards
against medical-sounding requests, and at checkout opens your items on Nykaa.com.

- **Real-AI mode:** run `server.py` (serves the page + a `/api/advise` endpoint backed by
  Gemini; your key stays on the server).
- **Zero-setup mode:** open `storefront.html` directly — with no server it falls back to a
  transparent rule-based brain, so the page always works.

## Cycle-aware skincare
A standout feature: a **Clue-style circular menstrual-cycle tracker** on the storefront.
Enter your last period date + cycle length (saved locally) and AuraAI reads your current
phase, explains how your skin tends to behave in it, and — on one tap — builds a **full
routine** matched to that phase:

| Phase | Skin tendency | Routine focus |
|---|---|---|
| Menstrual | dry, dull, sensitive | gentle hydration |
| Follicular | clear, glowing, resilient | actives / vitamin C |
| Ovulation | glowing, oil rising | light hydration + SPF |
| Luteal | oily, clogged, breakout-prone | oil control (salicylic / niacinamide) |

The phase→skin→product mapping is grounded in real hormonal-skin science, and the "Shop
for my skin right now" button runs through the same Gemini routine pipeline.

## Quickstart

```bash
pip install -r requirements.txt          # core: google-genai (optional: Chroma for vector RAG)
export GEMINI_API_KEY=...                # free key: https://aistudio.google.com/apikey

python server.py                         # the AuraAI storefront → http://localhost:8000
python demo.py                           # CLI demo of the advisor pipeline
streamlit run app/ui.py                  # plain chat UI
python -m evals.run_evals                # accuracy / safety / consistency scorecard
python test_pipeline.py                  # guided tour of the pipeline (intent/routing/critique)
```

**No key? Still runs.** Without `GEMINI_API_KEY` the advisor returns deterministic mock
output and the retriever uses the lexical fallback, so you can clone and run instantly.
Add the key to use the real Gemini pipeline; add Chroma + sentence-transformers for
semantic retrieval.

## What to read first
1. `docs/PROMPT_ITERATION_LOG.md` — failure → cause → fix, per prompt. The story of the
   engineering.
2. `prompts/templates.py` — the annotated, versioned prompt library.
3. `app/advisor.py` — the pipeline that ties it together.
4. `evals/run_evals.py` — how quality is measured.

## Repo layout
```
prompts/templates.py            versioned, annotated prompt library
app/advisor.py                  agent pipeline: parse → retrieve → route → generate → validate → critique
app/retrieval.py                RAG: vector (Chroma) + lexical fallback
app/ui.py                       Streamlit chat UI
server.py                       serves the storefront + Gemini-backed /api/advise endpoint
storefront.html                 the AuraAI storefront with the Nebula advisor (single file)
evals/cases.py                  test suite (accuracy / safety / consistency)
evals/run_evals.py              eval runner + scorecard
test_pipeline.py                guided tour / smoke test of the pipeline
data/products.csv               grounded product catalog (145 SKUs)
docs/PROMPT_ITERATION_LOG.md    failure→fix history (the key artifact)
docs/BEST_PRACTICES.md          methodology playbook
demo.py                         CLI demo
```

## Notes & data provenance
- The catalog (`data/products.csv`) has **145 products across 14 categories**, from three
  sources:
  - **`brand-verified` (40):** real products with real names + prices pulled from the
    brands' official stores (Minimalist, Dot & Key, Plum, The Derma Co, Pilgrim, etc.) —
    all genuinely sold on Nykaa, so checkout's Nykaa search surfaces the same items.
  - **`verified` (11):** real products hand-checked against public nykaa.com listings.
  - **`representative` (94):** real Indian beauty brands with realistic product types and
    plausible prices (brands without a pullable feed). Prices on these are illustrative.
  Note: Nykaa blocks automated access and has no public API, so live Nykaa data can't be
  scraped — `brand-verified` prices are the brand store's (Nykaa's may differ slightly),
  and checkout links out to Nykaa for the live price. Production would load Nykaa's live
  catalog via the **same schema** with no code changes.
- Product images on the storefront are pulled from brands' public Shopify CDNs (with an
  icon-tile fallback); the rest of the page is self-contained.
- **Why checkout opens a Nykaa *search*, not the cart:** a cart is private and tied to a
  logged-in Nykaa session, and there's no public "add to cart by URL" (Nykaa also blocks
  automation). A `?q=` search is the only reliable public entry point, so checkout sends
  all bagged items to one Nykaa search. A real Nykaa-internal build would call their cart
  API directly — same agent logic, only the final fulfilment call changes.
- Eval cases needing content judgment are scored only in LIVE mode (with a key); budget
  and hallucination checks run offline too.
- This is a prototype meant to demonstrate method, not a production system.
