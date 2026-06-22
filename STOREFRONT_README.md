# Beauty Advisor — Agent Storefront (demo)

A single-file mini "Nykaa" storefront with a **floating AI advisor** in the
bottom-right corner. You type what you want in plain language and the agent **takes
actions on your cart** — adds items, changes quantity, removes them, and walks you to
a checkout screen. It runs on the **real Nykaa product catalog** used by the rest of
this project.

## What it is
`storefront.html` — a mini storefront with a chat advisor. Two ways to run it:

- **Full / real-AI mode (recommended):** run the bundled server, which serves the
  page *and* powers the chat with the real Gemini brain (`app/advisor.py`):
  ```bash
  export GEMINI_API_KEY=...      # free key from https://aistudio.google.com/apikey
  python server.py               # then open http://localhost:8000
  ```
  The key stays on the server — it is never exposed to the browser. Without a key,
  the server still runs and returns deterministic mock recommendations.
- **Zero-setup mode:** just open `storefront.html` directly in a browser. With no
  server reachable, the chat transparently falls back to the offline rule-based
  brain, so the page still works with no install and no key.

## What the agent can do
- **Add to bag** from natural language: *"add a niacinamide serum"*,
  *"sunscreen for oily skin under 500"* → it picks the best catalog match and adds it.
- **Build a routine**: *"daytime routine for oily skin under 1500"* → adds a sensible
  cleanser → serum → sunscreen set within budget.
- **Edit the bag**: change quantity (+/−), remove an item, or *"clear my bag"*.
- **Checkout**: *"proceed to checkout"* → a simulated order-confirmation screen.
- **Stay safe**: medical-sounding requests (painful, bleeding, rash, eczema…) get a
  *see-a-dermatologist* response instead of product pushing.

## Why it's built this way (the honest design note)
A browser **extension that automates the real nykaa.com cart** is technically possible
but was deliberately **not** built: it depends on scraping a site we don't control
(breaks whenever Nykaa changes their page), raises terms-of-service and
account-security concerns, and exercises web-automation rather than the prompt /
agent skills this role is about. Real payment checkout can't and shouldn't be
automated from outside.

So the cart and checkout here are **simulated**. The point is to demonstrate the
**agentic workflow** — understand a request → take cart actions → reach checkout —
in a safe, self-contained way. In production, the same agent layer would call
**Nykaa's real cart/checkout APIs** instead of the in-page mock; nothing about the
agent logic changes.

## How the "brain" works
When the server is running, the chat's `handle()` sends each request to
`POST /api/advise`, which runs the **real Gemini-powered advisor** (`app/advisor.py`:
RAG retrieval → prompt → Gemini → JSON parse → anti-hallucination validation) and
returns grounded recommendations. The storefront then takes the cart actions
(add items, show total, walk to checkout) from that structured response.

If the backend is unreachable, `handle()` falls back to **transparent intent logic**
over the catalog (parse budget, detect category/concern/skin-type, match products,
safety guard) so the page still works offline. Pure UI actions (checkout, clear bag,
show bag) are always handled instantly client-side — they aren't AI tasks.
(See `app/advisor.py` and `prompts/templates.py` for the prompt-engineering side.)

## Try these
- `sunscreen for oily skin under 500`
- `add a niacinamide serum`
- `daytime routine for dry skin under 1500`
- `show me lipsticks`
- `proceed to checkout`
- `I have painful cystic acne` (safety response)

## Limitations
- Simulated cart/checkout; no real payment, no real Nykaa account.
- Catalog is 145 products across 14 categories: 25 verified from public Nykaa
  listings, ~120 representative demo entries (real brands, plausible prices). Not the
  full live inventory.
- With `server.py` running, the chat is Gemini-powered; opening the file directly
  (no server) falls back to rule-based intent logic.
