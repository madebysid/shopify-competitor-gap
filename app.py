import pandas as pd, streamlit as st
import scout

st.set_page_config(page_title="Shopify Product Scout Agent", page_icon="🛍️", layout="wide")
st.title("🛍️ Shopify Product Scout Agent")
st.caption("Scout a competitor collection, match it to your catalogue, price it, export a Shopify import CSV.")

with st.sidebar:
    st.header("Pricing rule")
    margin = st.slider("Target margin %", 0, 80, 40) / 100
    undercut = st.slider("Undercut competitor by %", 0, 30, 5) / 100
    st.header("Optional AI rewrite")
    provider = st.selectbox("Provider", ["None", "OpenAI", "Anthropic"])
    key = st.text_input("API key", type="password") if provider != "None" else ""

url = st.text_input("Competitor collection URL (leave empty for demo data)",
                    placeholder="https://store.example.com/collections/new")
own_file = st.file_uploader("Your catalogue CSV (columns: title, cost) - optional", type="csv")
limit = st.number_input("Max products", 1, 250, 50)

if st.button("Scout products", type="primary"):
    with st.spinner("Fetching products..."):
        products = scout.fetch_products(url.strip() or None, int(limit))
    if not products:
        st.error("No products found. Try the store's /collections/... URL or leave empty for demo data.")
        st.stop()
    own = pd.read_csv(own_file) if own_file else None
    products = scout.match(products, own)
    for p in products:
        p["our_price"] = scout.price_for(p["price"], p["cost"], margin, undercut)
        if provider != "None" and key:
            try:
                p["title"], p["body_html"] = scout.rewrite(p, provider, key)
            except Exception as e:
                st.warning(f"Rewrite failed for {p['handle']}: {e}")
    st.session_state.products = products

if products := st.session_state.get("products"):
    df = pd.DataFrame(products)[["image", "title", "product_type", "price", "our_price", "matched_title", "cost"]]
    st.success(f"{len(df)} products scouted, {int((df.matched_title != '').sum())} matched to your catalogue.")
    st.dataframe(df, column_config={"image": st.column_config.ImageColumn("Image"),
                                    "price": "Competitor", "our_price": "Our price"},
                 use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download Shopify import CSV", scout.to_shopify_csv(products),
                       "shopify_import.csv", "text/csv")
