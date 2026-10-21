import base64, json
from pathlib import Path
import pandas as pd, streamlit as st
import gap

st.set_page_config(page_title="Shopify Competitor Gap", page_icon="🔍", layout="wide")
st.title("🔍 Shopify Competitor Gap")
st.caption("Paste your store and a competitor's. See what you both sell and who's cheaper, what they sell that you don't, and what only you sell.")

EXAMPLE = Path(__file__).parent / "data" / "example.json"
if gap.IN_BROWSER:
    st.info("Browser demo: showing a cached real comparison. Browsers block requests to other stores (CORS), "
            "so to compare any two stores, run it locally: `pip install -r requirements.txt && streamlit run app.py`.")
    use_example = True
else:
    c1, c2 = st.columns(2)
    my_url = c1.text_input("My store URL", placeholder="https://mystore.com")
    their_url = c2.text_input("Competitor store URL", placeholder="https://competitor.com")
    use_example = st.checkbox("Use the cached example instead", value=not (my_url and their_url))
threshold = st.slider("Match threshold (fuzzy title score)", 60, 100, 85,
                      help="Higher = stricter. Same handle always matches; titles only match within the same vendor.")

if use_example:
    ex = json.loads(EXAMPLE.read_text())
    st.caption(f"Example: **{ex['mine']}** (as my store) vs **{ex['theirs']}**, cached {ex['fetched']}.")
    mine, theirs = pd.DataFrame(ex["mine_products"]), pd.DataFrame(ex["their_products"])
elif st.button("Compare", type="primary") or "cat" in st.session_state:
    if "cat" not in st.session_state or st.session_state.cat[0] != (my_url, their_url):
        with st.spinner("Pulling both catalogues from /products.json..."):
            try:
                st.session_state.cat = ((my_url, their_url), gap.fetch_catalogue(my_url), gap.fetch_catalogue(their_url))
            except Exception as e:
                st.error(f"Couldn't read /products.json ({e}). The store may not be on Shopify or may block it."); st.stop()
    _, mine, theirs = st.session_state.cat
else:
    st.stop()

@st.cache_data(show_spinner="Matching products...")
def run_match(mine, theirs, threshold):
    return gap.match_catalogues(mine, theirs, threshold)


covered, missing, unique = run_match(mine, theirs, threshold)
s = gap.summary(mine, theirs, covered, missing, unique)
m = st.columns(5)
m[0].metric("My products", s["my_products"]); m[1].metric("Their products", s["their_products"])
m[2].metric("I cover of theirs", f"{s['coverage_pct']}%"); m[3].metric("Avg price gap on overlaps", f"{s['avg_gap_pct']:+}%")
m[4].metric("Pricier / cheaper", f"{s['more_expensive']} / {s['cheaper']}")


def show(df, name):
    st.dataframe(df, use_container_width=True, hide_index=True) if not gap.IN_BROWSER else st.table(df.head(50))
    b64 = base64.b64encode(df.to_csv(index=False).encode()).decode()  # data-URI link works in stlite too
    st.markdown(f'<a download="{name}.csv" href="data:text/csv;base64,{b64}">⬇️ Download {name}.csv ({len(df)} rows)</a>',
                unsafe_allow_html=True)


t1, t2, t3 = st.tabs([f"Covered ({s['covered']})", f"Missing: they sell, I don't ({s['missing']})", f"Unique to me ({s['unique_to_me']})"])
with t1:
    show(covered[["my_title", "their_title", "my_price", "their_price", "diff", "diff_pct", "flag", "match_score", "my_url", "their_url"]], "covered")
with t2:
    st.caption("The opportunity list, most expensive first.")
    show(missing[["title", "vendor", "product_type", "price", "url"]], "missing")
with t3:
    show(unique[["title", "vendor", "product_type", "price", "url"]], "unique_to_me")
