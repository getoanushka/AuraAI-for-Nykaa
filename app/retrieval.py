"""
app/retrieval.py
================
Catalog retrieval for the Beauty Advisor — the "R" in RAG.

Two backends:
  1. VECTOR (preferred): embeds the catalog with sentence-transformers and stores
     vectors in Chroma. Retrieval is semantic cosine similarity. This is the path
     that demonstrates embeddings + a vector database.
  2. LEXICAL (fallback): a transparent attribute + keyword scorer with no external
     dependencies, so the project runs anywhere out-of-the-box.

We ground the LLM on retrieved rows instead of dumping the whole catalog. With 35
products it would all fit in context, but retrieval is the pattern that scales to
Nykaa's real catalog of 100k+ SKUs — and that scaling story is the point.
"""

import csv
import os
import re

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "products.csv")


def load_catalog():
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _row_text(r):
    """A natural-language blob per product, used for both embedding and keyword match."""
    return (
        f"{r['name']} by {r['brand']}. Category: {r['category']}. "
        f"For {r['concern']} on {r['skin_type']} skin. "
        f"Ingredients: {r['key_ingredients']}. Finish: {r['finish']}. "
        f"SPF {r['spf']}. ₹{r['price_inr']}."
    )


# --------------------------------------------------------------------------
# VECTOR BACKEND (preferred) — semantic retrieval via embeddings + Chroma
# --------------------------------------------------------------------------
def build_vector_index():
    """
    Build (or load) a Chroma collection of catalog embeddings.
    Requires: pip install chromadb sentence-transformers
    Returns a queryable Chroma collection, or None if libs are unavailable.
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None

    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.Client()
    try:
        col = client.get_collection("nykaa_products")
        return col  # already built this session
    except Exception:
        col = client.create_collection("nykaa_products")

    rows = load_catalog()
    texts = [_row_text(r) for r in rows]
    embeddings = model.encode(texts).tolist()
    col.add(
        ids=[r["product_id"] for r in rows],
        embeddings=embeddings,
        documents=texts,
        metadatas=rows,
    )
    return col


def vector_retrieve(query, k=8, max_price=None):
    col = build_vector_index()
    if col is None:
        return None  # signal caller to use lexical fallback
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    q_emb = model.encode([query]).tolist()
    res = col.query(query_embeddings=q_emb, n_results=min(k * 2, 35))
    rows = res["metadatas"][0]
    if max_price:
        rows = [r for r in rows if float(r["price_inr"]) <= max_price]
    return rows[:k]


# --------------------------------------------------------------------------
# LEXICAL BACKEND (fallback) — transparent attribute scoring, no dependencies
# --------------------------------------------------------------------------
# Map common query words (incl. plurals/synonyms) to the catalog's category names.
# Without this, "lipsticks" never matches the category "lip" and the scorer returns
# 0 for every row — silently falling back to catalog order (which starts with serums).
_CATEGORY_SYNONYMS = {
    "lipstick": "lip", "lipsticks": "lip", "lips": "lip", "lip": "lip",
    "lipbalm": "lip", "gloss": "lip",
    "sunscreen": "sunscreen", "sunscreens": "sunscreen", "sunblock": "sunscreen", "spf": "sunscreen",
    "moisturiser": "moisturizer", "moisturisers": "moisturizer",
    "moisturizer": "moisturizer", "moisturizers": "moisturizer",
    "cream": "moisturizer", "lotion": "moisturizer",
    "cleanser": "cleanser", "cleansers": "cleanser", "facewash": "cleanser", "wash": "cleanser",
    "serum": "serum", "serums": "serum", "toner": "toner", "toners": "toner",
    "foundation": "foundation", "concealer": "concealer", "primer": "primer",
    "mascara": "eye makeup", "kajal": "eye makeup", "eyeliner": "eye makeup", "eyeshadow": "eye makeup",
    "shampoo": "haircare", "conditioner": "haircare", "hair": "haircare",
    "mask": "mask", "scrub": "body care",
}


# Generic filler words to ignore in the query — otherwise loose stem-matching can
# misfire (e.g. "make" in "make it cheaper" prefix-matches "makeup" -> eye makeup).
_QUERY_STOPWORDS = {
    "make", "makes", "made", "it", "the", "a", "an", "for", "me", "my", "want",
    "need", "get", "got", "show", "find", "give", "good", "nice", "best", "cheap",
    "cheaper", "cheapest", "please", "some", "something", "under", "below", "budget",
    "with", "and", "to", "of", "in", "on", "is", "are", "i", "you", "can", "help",
}


def lexical_retrieve(query, k=8, max_price=None):
    rows = load_catalog()
    q = query.lower()
    tokens = {t for t in re.findall(r"[a-z]+", q) if t not in _QUERY_STOPWORDS}
    # canonical category names the query is asking for (via synonyms/plurals)
    wanted_categories = {_CATEGORY_SYNONYMS[t] for t in tokens if t in _CATEGORY_SYNONYMS}

    def _word_match(word):
        # exact, or a stem/plural overlap (e.g. "serums" <-> "serum") for words >= 4 chars
        if word in tokens:
            return True
        return any(len(t) >= 4 and (t.startswith(word) or word.startswith(t)) for t in tokens)

    def score(r):
        s = 0
        # strongest signal: the query names this product's category (handles plurals/synonyms)
        if r["category"].lower() in wanted_categories:
            s += 5
        # concern / skin_type / category / brand / ingredient word overlap
        for field, weight in (("concern", 3), ("skin_type", 3), ("category", 2),
                              ("brand", 2), ("key_ingredients", 1)):
            for word in re.findall(r"[a-z]+", r[field].lower()):
                if _word_match(word):
                    s += weight
        return s

    scored = [(score(r), r) for r in rows]
    scored = [(sc, r) for sc, r in scored if sc > 0] or [(0, r) for r in rows]
    scored.sort(key=lambda x: x[0], reverse=True)
    out = [r for _, r in scored]
    if max_price:
        out = [r for r in out if float(r["price_inr"]) <= max_price]
    return out[:k]


def retrieve(query, k=8, max_price=None):
    """Try vector retrieval; fall back to lexical. This is what the app calls."""
    rows = vector_retrieve(query, k=k, max_price=max_price)
    backend = "vector"
    if rows is None:
        rows = lexical_retrieve(query, k=k, max_price=max_price)
        backend = "lexical"
    return rows, backend


def catalog_block(rows):
    """Render retrieved rows as the <catalog> text injected into the prompt."""
    lines = []
    for r in rows:
        lines.append(
            f"- id={r['product_id']} | {r['name']} ({r['brand']}) | "
            f"{r['category']} | for {r['concern']} / {r['skin_type']} skin | "
            f"SPF {r['spf']} | ₹{r['price_inr']}"
        )
    return "\n".join(lines)
