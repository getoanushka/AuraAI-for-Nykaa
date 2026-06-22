# Prompt Engineering Best Practices

A short, opinionated playbook distilled from building this project. Written to match
the way the role describes the work: design, evaluate, document, repeat.

## 1. Choose the technique deliberately
- **Zero-shot** for clear, common tasks where the model already knows the format
  (our system persona).
- **Few-shot** when you need a *specific, stable output shape* or have tricky edge
  cases (our query parser — two examples lock in the null-budget convention).
- **Chain-of-thought** when the task needs intermediate reasoning, like arithmetic or
  multi-step ordering (our budget math and routine sequencing). Keep the reasoning
  internal and emit only the final structured answer.

## 2. Put durable rules in the system prompt
Persona, safety boundaries, and hard constraints belong in the system role — set once,
applied every turn. Number them; imperative numbered rules are followed more reliably
than the same content as prose.

## 3. Ground before you generate (RAG)
For anything tied to real inventory/knowledge, retrieve the relevant records and inject
them into the prompt, then constrain the model to use only those. This is the single
biggest lever against hallucination in e-commerce.

## 4. Demand structured output, but don't trust it blindly
Specify an exact JSON schema. Then write tolerant parsing (strip code fences, extract
the outermost object) and a validator that re-checks anything business-critical
(valid IDs, budget totals). Prompt + code, not prompt alone.

## 5. Evaluate on explicit axes
Define what "good" means and test it. Here: **accuracy** (right products, budget met),
**safety** (no medical claims, dermatologist referrals), **consistency** (same input →
same recommendations across runs). Keep cases as data so the benchmark grows over time.

## 6. Version prompts and log iterations
Treat prompts like code: version them, and keep a log of failure → cause → fix. The log
is how you (and your team) avoid re-introducing solved bugs and how you demonstrate
judgment.

## 7. Optimize for the deployment, not the demo
A prompt that works once in a playground is not done. The questions that matter:
Does it fail safely? Is the output machine-consumable? Does it stay within cost/latency?
Is it consistent enough to ship?
