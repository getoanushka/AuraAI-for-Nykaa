"""
demo.py
=======
Quick command-line demo. Run:  python demo.py
"""

import json
from app.advisor import advise

EXAMPLES = [
    ("Build a daytime routine for oily, acne-prone skin under 2000", 2000),
    ("Cheapest sunscreen for oily skin", None),
    ("suggest something nice", None),  # vague -> should ask a clarifying question (live)
]

if __name__ == "__main__":
    for q, budget in EXAMPLES:
        print("\n" + "=" * 70)
        print(f"USER: {q}  (budget: {budget})")
        print("-" * 70)
        res = advise(q, max_price=budget)
        print(f"[retrieval: {res['retrieval_backend']} | valid: {res['valid']}]")
        print(json.dumps(res["answer"], indent=2, ensure_ascii=False))
