"""
build_catalog.py
================
Generates a representative demo catalog of ~150 beauty products across real Indian
brands and many categories, written to data/products.csv.

IMPORTANT: This is REPRESENTATIVE demo data — real brand names and realistic product
types/prices, but prices are illustrative, not live-verified Nykaa prices. In
production the same schema would be populated from Nykaa's live catalog. The first
25 rows are the originally web-verified products; the rest are generated.
"""

import csv
import os

VERIFIED = [
    # the originally search-verified products (kept as-is, marked source=verified)
    ("Minimalist 10% Niacinamide Face Serum With Matmarine + Zinc","Minimalist","serum","oily skin","oily","niacinamide, zinc PCA, aloe vera",599,"liquid",0,"30ml"),
    ("Minimalist 5% Niacinamide Face Serum With Bifida Ferment","Minimalist","serum","acne","oily","niacinamide, bifida ferment, oat",599,"liquid",0,"30ml"),
    ("Minimalist 2% Salicylic Acid Face Serum","Minimalist","serum","acne","oily","salicylic acid, zinc, LHA",549,"liquid",0,"30ml"),
    ("Minimalist 16% Vitamin C Face Serum With Vitamin E & Ferulic Acid","Minimalist","serum","dullness","all","vitamin C, vitamin E, ferulic acid",699,"liquid",0,"30ml"),
    ("Minimalist 2% Hyaluronic Acid + PGA Face Serum","Minimalist","serum","dryness","dry","hyaluronic acid, PGA, vitamin B5",599,"liquid",0,"30ml"),
    ("Minimalist 2% Alpha Arbutin Face Serum With Butylresorcinol","Minimalist","serum","pigmentation","all","alpha arbutin, butylresorcinol",699,"liquid",0,"30ml"),
    ("Minimalist 8% Glycolic Acid Exfoliating Toner","Minimalist","toner","dullness","all","glycolic acid, geranium water",549,"liquid",0,"100ml"),
    ("Minimalist 2% Salicylic Acid + LHA Face Cleanser With Zinc","Minimalist","cleanser","oily skin","oily","salicylic acid, LHA, zinc",349,"gel",0,"100ml"),
    ("Minimalist SPF 50 PA++++ Sunscreen With Niacinamide","Minimalist","sunscreen","oily skin","oily","niacinamide, hybrid UV filters",399,"matte",50,"50ml"),
    ("Minimalist Vitamin K + Retinal 01% Under Eye Cream With Caffeine","Minimalist","eye care","dark circles","all","vitamin K, retinal, caffeine",599,"cream",0,"15ml"),
    ("Dot & Key Vitamin C + E Super Bright Sunscreen SPF 50+ PA++++","Dot & Key","sunscreen","dullness","all","vitamin C, vitamin E, UV filters",445,"dewy",50,"50ml"),
    ("Dot & Key Watermelon Cooling Sunscreen SPF 50+ PA++++","Dot & Key","sunscreen","sensitivity","sensitive","watermelon extract, hyaluronic acid",445,"dewy",50,"50ml"),
    ("Dot & Key Blueberry Hydrate Barrier Repair Sunscreen SPF 50+","Dot & Key","sunscreen","dryness","dry","blueberry, ceramides, hyaluronic acid",445,"dewy",50,"50ml"),
    ("Dot & Key Vitamin C + E 100% Mineral Sunscreen SPF 50+ PA++++","Dot & Key","sunscreen","sensitivity","sensitive","zinc oxide, vitamin C, vitamin E",595,"matte",50,"50ml"),
    ("Dot & Key Strawberry Dew Tinted Sunscreen SPF 50+","Dot & Key","sunscreen","coverage","all","strawberry extract, tint, UV filters",549,"tinted",50,"50ml"),
    ("Cetaphil Gentle Skin Cleanser","Cetaphil","cleanser","sensitivity","sensitive","glycerin, panthenol, niacinamide",399,"cream",0,"125ml"),
    ("Plum Green Tea Pore Cleansing Gel Face Wash With Glycolic Acid","Plum","cleanser","oily skin","oily","green tea, glycolic acid",345,"gel",0,"100ml"),
    ("Maybelline New York Super Stay Matte Ink Liquid Lipstick - Lover","Maybelline","lip","longwear","all","dimethicone, pigment",749,"matte",0,"5ml"),
    ("Maybelline New York Super Stay Vinyl Ink Liquid Lipstick","Maybelline","lip","longwear","all","shine polymers, pigment",799,"glossy",0,"4.2ml"),
    ("Maybelline New York Fit Me Matte + Poreless 16H Foundation","Maybelline","foundation","oily skin","oily","perlite, micro-powders",549,"matte",0,"30ml"),
    ("Maybelline New York Fit Me Primer Oil-Free","Maybelline","primer","oily skin","oily","glycerin, blurring polymers",425,"matte",0,"30ml"),
    ("Maybelline New York The Colossal Kajal","Maybelline","eye makeup","longwear","sensitive","carnauba wax, pigment",225,"matte",0,"0.35g"),
    ("Maybelline New York Hypercurl Waterproof Mascara","Maybelline","eye makeup","longwear","all","film-forming polymers",299,"matte",0,"9.2ml"),
    ("Maybelline New York Lifter Gloss Tinted Lip Gloss","Maybelline","lip","dryness","all","hyaluronic acid, tint",699,"glossy",0,"5.4ml"),
    ("Maybelline New York Instant Age Rewind Concealer","Maybelline","concealer","dark circles","all","goji berry, haloxyl",699,"natural",0,"6ml"),
]

# Generation building blocks for representative products
GEN = {
    "serum": {
        "brands": ["The Derma Co","Dot & Key","Plum","Mamaearth","Pilgrim","Sugar Pop","Foxtale","RE'EQUIL","Deconstruct","Minimalist"],
        "variants": [
            ("10% Vitamin C Face Serum","dullness","all","vitamin C, ferulic acid","liquid",(499,699)),
            ("1% Hyaluronic + B5 Serum","dryness","dry","hyaluronic acid, vitamin B5","liquid",(399,599)),
            ("5% Niacinamide Serum","oily skin","oily","niacinamide, zinc","liquid",(399,549)),
            ("2% Salicylic Acid Serum","acne","oily","salicylic acid","liquid",(449,599)),
            ("Retinol 0.3% Night Serum","aging","all","retinol, squalane","liquid",(599,899)),
            ("Alpha Arbutin Serum","pigmentation","all","alpha arbutin","liquid",(499,699)),
            ("Peptide Firming Serum","aging","all","peptides, niacinamide","liquid",(699,999)),
            ("Centella Soothing Serum","sensitivity","sensitive","centella, panthenol","liquid",(449,649)),
        ],
        "sizes": ["30ml"], "spf": 0,
    },
    "cleanser": {
        "brands": ["Cetaphil","Plum","Mamaearth","The Derma Co","Simple","Sebamed","Foxtale","Minimalist"],
        "variants": [
            ("Gentle Foaming Face Wash","sensitivity","sensitive","glycerin, panthenol","foam",(249,449)),
            ("Salicylic Acid Face Wash","oily skin","oily","salicylic acid, tea tree","gel",(249,399)),
            ("Vitamin C Brightening Face Wash","dullness","all","vitamin C","gel",(249,399)),
            ("Ubtan Glow Face Wash","dullness","all","turmeric, saffron","cream",(199,349)),
            ("Hydrating Cream Cleanser","dryness","dry","glycerin, ceramides","cream",(299,499)),
            ("Charcoal Detox Face Wash","oily skin","oily","activated charcoal","foam",(249,399)),
        ],
        "sizes": ["100ml","150ml"], "spf": 0,
    },
    "moisturizer": {
        "brands": ["Cetaphil","Neutrogena","Dot & Key","Plum","Mamaearth","Re'equil","Minimalist","Pond's"],
        "variants": [
            ("Oil-Free Gel Moisturizer","oily skin","oily","niacinamide, glycerin","gel",(299,549)),
            ("Ceramide Barrier Cream","dryness","dry","ceramides, shea butter","cream",(399,695)),
            ("Aloe Soothing Gel","sensitivity","sensitive","aloe vera, chamomile","gel",(199,399)),
            ("Vitamin C Day Cream","dullness","all","vitamin C, SPF","cream",(399,599)),
            ("Hyaluronic Water Cream","dryness","all","hyaluronic acid","gel",(349,595)),
            ("Night Repair Cream","aging","all","retinol, peptides","cream",(499,899)),
        ],
        "sizes": ["50ml","80ml"], "spf": 0,
    },
    "sunscreen": {
        "brands": ["Dot & Key","Minimalist","The Derma Co","Re'equil","Aqualogica","Foxtale","La Shield","Lakme"],
        "variants": [
            ("Ultra Light Gel Sunscreen SPF 50","oily skin","oily","hybrid UV filters","matte",(349,595)),
            ("Hydrating Sunscreen SPF 50 PA++++","dryness","dry","hyaluronic acid, UV filters","dewy",(395,595)),
            ("Mineral Sunscreen SPF 30","sensitivity","sensitive","zinc oxide, titanium dioxide","matte",(449,650)),
            ("Tinted Sunscreen SPF 50","coverage","all","tint, UV filters","tinted",(449,649)),
            ("Vitamin C Glow Sunscreen SPF 50","dullness","all","vitamin C, UV filters","dewy",(395,595)),
        ],
        "sizes": ["50ml"], "spf": 50,
    },
    "toner": {
        "brands": ["Minimalist","Plum","Dot & Key","The Derma Co","Pilgrim"],
        "variants": [
            ("Rose Hydrating Toner","dryness","dry","rose water, glycerin","liquid",(295,445)),
            ("Salicylic Acid Pore Toner","oily skin","oily","salicylic acid, witch hazel","liquid",(395,549)),
            ("Glycolic Acid Exfoliating Toner","dullness","all","glycolic acid","liquid",(449,599)),
            ("Green Tea Clarifying Toner","oily skin","oily","green tea, niacinamide","liquid",(295,445)),
        ],
        "sizes": ["100ml","150ml"], "spf": 0,
    },
    "mask": {
        "brands": ["Plum","Mamaearth","The Face Shop","Garnier","Innisfree","Sugar Pop"],
        "variants": [
            ("Clay Detox Face Mask","oily skin","oily","kaolin clay, charcoal","clay",(299,499)),
            ("Overnight Sleeping Mask","dryness","dry","hyaluronic acid, niacinamide","gel",(395,645)),
            ("Brightening Sheet Mask","dullness","all","vitamin C","sheet",(49,149)),
            ("Soothing Aloe Mask","sensitivity","sensitive","aloe, centella","gel",(199,399)),
        ],
        "sizes": ["50g","100g","25g"], "spf": 0,
    },
    "lip": {
        "brands": ["Sugar","Maybelline","Lakme","Nykaa Cosmetics","Sugar Pop","MyGlamm","Faces Canada"],
        "variants": [
            ("Matte Liquid Lipstick","longwear","all","vitamin E, pigment","matte",(299,699)),
            ("Creamy Bullet Lipstick","longwear","all","shea butter, pigment","cream",(299,599)),
            ("Tinted Lip Balm","dryness","all","shea butter, vitamin E","sheer",(199,399)),
            ("Glossy Lip Oil","dryness","all","jojoba oil, vitamin E","glossy",(299,499)),
        ],
        "sizes": ["4g","5ml","7ml"], "spf": 0,
        "shades": ["Brick Red","Mauve Nude","Coral Crush","Berry Bold","Pink Pout","Toffee Brown"],
    },
    "foundation": {
        "brands": ["Lakme","Maybelline","L'Oreal Paris","Nykaa Cosmetics","Faces Canada","SUGAR"],
        "variants": [
            ("Matte Liquid Foundation","oily skin","oily","perlite, silica","matte",(449,899)),
            ("Hydrating Serum Foundation","dryness","dry","hyaluronic acid","dewy",(549,999)),
            ("Buildable Natural Foundation","coverage","all","glycerin, vitamin E","natural",(499,899)),
        ],
        "sizes": ["30ml"], "spf": 15,
        "shades": ["Fair","Light","Natural","Wheatish","Honey","Caramel","Deep"],
    },
    "eye makeup": {
        "brands": ["Maybelline","Lakme","Sugar","Nykaa Cosmetics","Faces Canada","MyGlamm"],
        "variants": [
            ("Intense Kajal","longwear","sensitive","carnauba wax","matte",(149,349)),
            ("Volumizing Mascara","longwear","all","film polymers","matte",(299,599)),
            ("Liquid Eyeliner","longwear","all","pigment, polymers","matte",(199,449)),
            ("Eyeshadow Palette","coverage","all","mica, pigment","shimmer",(499,1299)),
        ],
        "sizes": ["1.2g","9ml","2.5ml","10g"], "spf": 0,
    },
    "haircare": {
        "brands": ["Mamaearth","WOW Skin Science","Pilgrim","The Tribe Concepts","L'Oreal Paris","Tresemme"],
        "variants": [
            ("Onion Hair Growth Shampoo","hair fall","all","onion oil, biotin","liquid",(299,499)),
            ("Rosemary Scalp Serum","hair fall","all","rosemary, redensyl","liquid",(399,699)),
            ("Anti-Dandruff Shampoo","dandruff","all","ketoconazole, tea tree","liquid",(299,549)),
            ("Hair Repair Conditioner","dryness","dry","argan oil, keratin","cream",(299,549)),
            ("Hair Growth Oil","hair fall","all","bhringraj, amla","oil",(249,449)),
        ],
        "sizes": ["100ml","200ml","250ml"], "spf": 0,
    },
    "body care": {
        "brands": ["Plum","Mamaearth","Nivea","The Body Shop","Dove","Cetaphil"],
        "variants": [
            ("Body Lotion Deep Moisture","dryness","dry","shea butter, glycerin","cream",(199,499)),
            ("Vitamin C Body Wash","dullness","all","vitamin C","gel",(199,399)),
            ("Coffee Body Scrub","dullness","all","coffee, walnut","scrub",(299,549)),
            ("Soothing Body Butter","dryness","sensitive","cocoa butter, aloe","cream",(395,795)),
        ],
        "sizes": ["200ml","300ml","100g"], "spf": 0,
    },
}


def mid(lo, hi):
    """Deterministic 'price' = rounded midpoint to keep things stable/plausible."""
    p = (lo + hi) // 2
    return int(round(p / 5.0) * 5)  # round to nearest 5, like real INR prices


def build():
    rows = []
    pid = 1

    def add(name, brand, cat, concern, skin, ingr, price, finish, spf, size, source):
        nonlocal pid
        rows.append({
            "product_id": f"P{pid:03d}", "name": name, "brand": brand, "category": cat,
            "concern": concern, "skin_type": skin, "key_ingredients": ingr,
            "price_inr": float(price), "finish": finish, "spf": int(spf),
            "size": size, "source": source,
        })
        pid += 1

    # 1) verified first
    for v in VERIFIED:
        name, brand, cat, concern, skin, ingr, price, finish, spf, size = v
        add(name, brand, cat, concern, skin, ingr, price, finish, spf, size, "verified")

    # 2) generated representative products
    for cat, cfg in GEN.items():
        brands = cfg["brands"]
        sizes = cfg["sizes"]
        bi = 0
        for vi, variant in enumerate(cfg["variants"]):
            vname, concern, skin, ingr, finish, (lo, hi) = variant
            shades = cfg.get("shades")
            # make a few brand/shade combinations per variant
            combos = shades if shades else [None]
            for j, shade in enumerate(combos[:4] if shades else [None, None]):
                brand = brands[bi % len(brands)]; bi += 1
                size = sizes[(vi + j) % len(sizes)]
                price = mid(lo, hi) + (j * 10)  # slight spread
                if shade:
                    name = f"{brand} {vname} - {shade}"
                else:
                    name = f"{brand} {vname}"
                add(name, brand, cat, concern, skin, ingr, price, finish, cfg["spf"], size, "representative")

    return rows


def main():
    rows = build()
    out = os.path.join(os.path.dirname(__file__), "data", "products.csv")
    cols = ["product_id","name","brand","category","concern","skin_type",
            "key_ingredients","price_inr","finish","spf","size","source"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {len(rows)} products to {out}")
    # quick category breakdown
    from collections import Counter
    c = Counter(r["category"] for r in rows)
    for k, v in sorted(c.items()):
        print(f"  {k:<14} {v}")


if __name__ == "__main__":
    main()
