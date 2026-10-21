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
