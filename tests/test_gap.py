import sys, pathlib
import pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
import gap

def cat(rows):
    return pd.DataFrame([dict(zip(["handle", "title", "vendor", "price"], r), product_type="", url="") for r in rows])

MINE = cat([("af1-white", "Nike Air Force 1 Low - White", "Nike", 110), ("nb-990", "New Balance 990v6 Grey", "New Balance", 200),
            ("my-tee", "House Logo Tee", "Mine", 40)])
THEIRS = cat([("nike-af1-low-white", "NIKE AIR FORCE 1 LOW (WHITE)", "Nike", 100), ("nb-990", "NB 990 v6", "New Balance", 210),
              ("samba", "Adidas Samba OG", "adidas", 120), ("af1-fake", "Nike Air Force 1 Low - White", "Reebok", 90)])

def test_match_views_and_summary():
    cov, miss, uniq = gap.match_catalogues(MINE, THEIRS, threshold=85)
    assert len(cov) == 2                                   # fuzzy title + same handle; other vendor ignored
    af1 = cov[cov.my_title.str.startswith("Nike")].iloc[0]
    assert af1["diff"] == 10 and af1.diff_pct == 10.0 and af1.flag == "I'm more expensive"
    assert cov[cov.vendor == "New Balance"].iloc[0].flag == "I'm cheaper"
    assert list(miss.title) == ["Adidas Samba OG", "Nike Air Force 1 Low - White"]   # sorted by price desc
    assert list(uniq.title) == ["House Logo Tee"]
    s = gap.summary(MINE, THEIRS, cov, miss, uniq)
    assert s["coverage_pct"] == 50.0 and s["more_expensive"] == 1 and s["cheaper"] == 1

def test_fetch_paginates():
    pages = {1: [{"handle": f"p{i}", "title": "x", "variants": [{"price": "9"}, {"price": "5"}]} for i in range(250)],
             2: [{"handle": "last", "title": "y", "variants": [{"price": "7"}]}]}
    calls = []
    df = gap.fetch_catalogue("shop.example", get=lambda u, p: (calls.append(p["page"]), {"products": pages.get(p["page"], [])})[1])
    assert calls == [1, 2] and len(df) == 251 and df.price.iloc[0] == 5.0
    assert df.url.iloc[-1] == "https://shop.example/products/last"
