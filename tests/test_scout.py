import sys, pathlib, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
import scout

def test_round_and_price():
    assert scout.round_99(18.2) == 17.99 and scout.round_99(18.2, up=True) == 18.99
    assert scout.price_for(20.0, undercut=0.1) == 17.99          # 18.0 -> 17.99
    assert scout.price_for(20.0, cost=15, margin=0.4) == 25.99   # margin floor wins

def test_demo_pipeline_exports_csv():
    own = pd.read_csv(pathlib.Path(scout.__file__).parent / "data/demo_own_catalogue.csv")
    ps = scout.match(scout.fetch_products(None), own)
    assert len(ps) == 15 and sum(bool(p["matched_title"]) for p in ps) == 5
    for p in ps: p["our_price"] = scout.price_for(p["price"], p["cost"])
    csv = scout.to_shopify_csv(ps)
    assert csv.startswith("Handle,Title") and csv.count("\n") == 16

def test_own_catalogue_paginates_and_uses_cost_proxy():
    pages = {1: [{"title": f"P{i}", "variants": [{"price": "10.00"}]} for i in range(250)],
             2: [{"title": "Last", "variants": [{"price": "40.00"}]}]}
    calls = []
    def fake_get(url, params):
        calls.append(params["page"]); return {"products": pages.get(params["page"], [])}
    df = scout.fetch_own_catalogue("https://x.com/", cost_pct=0.3, get=fake_get)
    assert calls == [1, 2] and len(df) == 251
    assert df.iloc[-1].cost == 12.0 and list(df.columns) == ["title", "price", "cost"]
