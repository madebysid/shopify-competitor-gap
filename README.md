# 🛍️ Shopify Product Scout Agent

Point it at a competitor's Shopify collection, match what they sell against your own catalogue, price every product with a clear rule, optionally let an LLM rewrite the copy, and download a ready-to-import Shopify CSV.

**[▶ Live demo](https://madebysid.github.io/shopify-product-scout-agent/)**: runs fully in your browser with [stlite](https://github.com/whitphx/stlite), on demo data (first load takes ~30s).

![screenshot](assets/screenshot.png)

This is a small, open version of the product engine I built as Technical Director at EcomVest, which took catalogue output across our Shopify stores from about 100 to about 1,000 products a week.

## Features
- **Scrape any collection**: reads Shopify's `/products.json` when the store exposes it, falls back to HTML parsing with requests + BeautifulSoup.
- **Runs with no key**: leave the URL empty to use 15 bundled demo products (`data/demo_competitor.json`).
- **Catalogue matching**: upload a `title,cost` CSV, or enter **My store URL** to pull your own catalogue from `/products.json` (paginated). Shopify's public JSON has no cost, so cost = price × a cost-% slider you set. Titles are fuzzy-matched.
- **Pricing rule**: undercut the competitor by X%, never below `cost / (1 - target margin)`, snapped to `.99`.
- **Optional AI rewrite**: bring your own OpenAI or Anthropic key to rewrite titles and descriptions.
- **Shopify import CSV**: products export as drafts, with the competitor price as compare-at.

## Setup
```bash
pip install -r requirements.txt
streamlit run app.py
```
Try it with `data/demo_own_catalogue.csv` as your catalogue.

## Browser demo vs local
The GitHub Pages demo (`docs/`) runs on Pyodide. Browsers block cross-site requests (CORS), so live URL scraping and My store URL are turned off there. Run locally or on Streamlit Cloud for real stores. `docs/app.py` and `docs/scout.py` are copies of the root files.

## How it works
1. `scout.fetch_products()` tries `<collection>/products.json`, then HTML product cards.
2. `scout.match()` fuzzy-matches titles (`difflib`) to your catalogue.
3. `scout.price_for()` applies undercut → margin floor → `.99` rounding.
4. `scout.rewrite()` (optional) calls the chosen LLM and asks for JSON.
5. `scout.to_shopify_csv()` writes Shopify's product import columns.

Tests: `pip install pytest && pytest -q`

Only scrape stores whose terms allow it, and review AI-written copy before publishing.

## Author
Siddharth Kumar · [sidailab.com](https://sidailab.com) · MIT licensed
