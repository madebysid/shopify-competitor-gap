"""Shopify competitor gap: pull two catalogues, match products, report overlap, gaps and price differences."""
import re, sys
import pandas as pd
try:
    from rapidfuzz import fuzz, process
except ImportError:  # Pyodide has no rapidfuzz wheel: small difflib stand-in for the browser demo
    from difflib import SequenceMatcher

    class fuzz:
        @staticmethod
        def token_sort_ratio(a, b):
            return SequenceMatcher(None, " ".join(sorted(a.split())), " ".join(sorted(b.split()))).ratio() * 100

    class process:
        @staticmethod
        def extractOne(q, choices, scorer, score_cutoff=0):
            best = max(((c, scorer(q, c), k) for k, c in choices.items()), key=lambda x: x[1], default=None)
            return best if best and best[1] >= score_cutoff else None

IN_BROWSER = sys.platform == "emscripten"  # stlite / Pyodide: CORS blocks live store requests
UA = {"User-Agent": "Mozilla/5.0 (shopify-competitor-gap)"}
COLS = ["handle", "title", "vendor", "product_type", "price", "url"]


def fetch_catalogue(store_url, max_pages=10, get=None):
    """All products from <store>/products.json, 250 per page. Price = lowest variant price."""
    if get is None:
        import requests
        get = lambda u, p: requests.get(u, params=p, headers=UA, timeout=20).json()
    base = store_url.strip().split("?")[0].rstrip("/")
    base = base if base.startswith("http") else "https://" + base
    rows = []
    for page in range(1, max_pages + 1):
        batch = get(f"{base}/products.json", {"limit": 250, "page": page}).get("products", [])
        for p in batch:
            prices = [float(v["price"]) for v in p.get("variants", []) if v.get("price")]
            rows.append({"handle": p.get("handle", ""), "title": p.get("title", ""), "vendor": p.get("vendor", ""),
                         "product_type": p.get("product_type", ""), "price": min(prices) if prices else None,
                         "url": f"{base}/products/{p.get('handle', '')}"})
        if len(batch) < 250:
            break
    return pd.DataFrame(rows, columns=COLS).drop_duplicates("handle")


def norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", str(s).lower()).strip()


SIZE_TAGS = {"ps", "td", "gs", "kids", "kid", "toddler", "infant", "infants", "youth", "baby", "womens", "women", "wmns"}


def size_group(title):
    """Kids/women's tags in a title. Products only match if these agree (adult != kids sizes)."""
    return frozenset(SIZE_TAGS & set(norm(title).replace("women s", "womens").split()))


def match_catalogues(mine, theirs, threshold=85):
    """For each competitor product, find my best match: same handle wins, else fuzzy title within the same vendor
    and the same size group (kids/women's tags)."""
    mine = mine.reset_index(drop=True)
    my_handles = {h: i for i, h in enumerate(mine.handle)}
    my_titles = [norm(t) for t in mine.title]
    my_vendors = [norm(v) for v in mine.vendor]
    my_groups = [size_group(t) for t in mine.title]
    pairs = []
    for _, t in theirs.iterrows():
        if t.handle in my_handles:
            pairs.append((t, mine.loc[my_handles[t.handle]], 100.0)); continue
        v, g = norm(t.vendor), size_group(t.title)
        cand = {i: my_titles[i] for i in range(len(mine))
                if (not v or not my_vendors[i] or my_vendors[i] == v) and my_groups[i] == g}
        hit = process.extractOne(norm(t.title), cand, scorer=fuzz.token_sort_ratio, score_cutoff=threshold)
        if hit:
            pairs.append((t, mine.loc[hit[2]], round(hit[1], 1)))
    covered = pd.DataFrame([{
        "my_title": m.title, "their_title": t.title, "vendor": t.vendor, "my_price": m.price, "their_price": t.price,
        "diff": round(m.price - t.price, 2) if pd.notna(m.price) and pd.notna(t.price) else None,
        "match_score": s, "my_url": m.url, "their_url": t.url} for t, m, s in pairs],
        columns=["my_title", "their_title", "vendor", "my_price", "their_price", "diff", "match_score", "my_url", "their_url"])
    covered["diff_pct"] = (covered["diff"] / covered["their_price"] * 100).round(1)
    covered["flag"] = covered["diff"].apply(lambda d: "I'm more expensive" if d > 0 else ("I'm cheaper" if d < 0 else "Same price"))
    matched_theirs = {t.handle for t, _, _ in pairs}
    matched_mine = {m.handle for _, m, _ in pairs}
    missing = theirs[~theirs.handle.isin(matched_theirs)].sort_values("price", ascending=False)
    unique = mine[~mine.handle.isin(matched_mine)].sort_values("price", ascending=False)
    return covered.sort_values("diff_pct", ascending=False), missing, unique


def summary(mine, theirs, covered, missing, unique):
    n_cov_theirs = len(theirs) - len(missing)
    return {"my_products": len(mine), "their_products": len(theirs), "covered": len(covered),
            "missing": len(missing), "unique_to_me": len(unique),
            "coverage_pct": round(n_cov_theirs / len(theirs) * 100, 1) if len(theirs) else 0.0,
            "avg_gap_pct": float(round(covered["diff_pct"].mean(), 1)) if len(covered) else 0.0,
            "more_expensive": int((covered["diff"] > 0).sum()), "cheaper": int((covered["diff"] < 0).sum())}
