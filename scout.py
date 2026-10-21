"""Core logic: fetch competitor products, match, price, rewrite, export."""
import json, math, re, difflib
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd, requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (product-scout-agent)"}
DEMO = Path(__file__).parent / "data" / "demo_competitor.json"


def load_demo():
    return json.loads(DEMO.read_text())


def _from_products_json(url, limit):
    """Shopify stores expose /products.json (or /collections/x/products.json)."""
    base = url.split("?")[0].rstrip("/")
    r = requests.get(f"{base}/products.json", params={"limit": limit}, headers=UA, timeout=15)
    if r.status_code != 200 or "products" not in r.text[:200]:
        return []
    out = []
    for p in r.json().get("products", []):
        v = (p.get("variants") or [{}])[0]
        img = (p.get("images") or [{}])
        out.append({"handle": p.get("handle"), "title": p.get("title"),
                    "product_type": p.get("product_type", ""), "vendor": p.get("vendor", ""),
                    "price": float(v.get("price") or 0), "body_html": p.get("body_html") or "",
                    "image": img[0].get("src", "") if img else ""})
    return out


def _from_html(url, limit):
    """Fallback: parse product cards from any storefront HTML."""
    soup = BeautifulSoup(requests.get(url, headers=UA, timeout=15).text, "html.parser")
    out, seen = [], set()
    for a in soup.select("a[href*='/products/']"):
        handle = urlparse(a["href"]).path.split("/products/")[-1].strip("/")
        card = a.find_parent(["li", "div", "article"]) or a
        text = card.get_text(" ", strip=True)
        m = re.search(r"(\d+[.,]?\d*)", text.split("$")[-1] if "$" in text else "")
        if not handle or handle in seen or not m:
            continue
        seen.add(handle)
        img = card.find("img")
        out.append({"handle": handle, "title": a.get_text(strip=True) or handle.replace("-", " ").title(),
                    "product_type": "", "vendor": urlparse(url).netloc, "price": float(m.group(1).replace(",", "")),
                    "body_html": "", "image": (img.get("src") or "") if img else ""})
        if len(out) >= limit:
            break
    return out


def fetch_products(url=None, limit=50):
    if not url:
        return load_demo()
    try:
        return _from_products_json(url, limit) or _from_html(url, limit)
    except requests.RequestException:
        return []


def round_99(x, up=False):
    """Snap to a .99 ending: down (stay under x) by default, up when x is a floor."""
    r = math.floor(x) + 0.99
    if up:
        return round(r, 2)
    return round(r - 1 if r > x else r, 2)


def price_for(comp_price, cost=None, margin=0.4, undercut=0.05):
    """Undercut the competitor, but never go below cost / (1 - margin)."""
    price = round_99(comp_price * (1 - undercut))
    if cost:
        price = max(price, round_99(cost / (1 - margin), up=True))
    return price


def match(products, own=None, cutoff=0.6):
    """Fuzzy title match against an own-catalogue DataFrame (columns: title, cost)."""
    titles = list(own["title"]) if own is not None else []
    for p in products:
        hit = difflib.get_close_matches(p["title"], titles, 1, cutoff)
        p["matched_title"] = hit[0] if hit else ""
        p["cost"] = float(own.loc[own["title"] == hit[0], "cost"].iloc[0]) if hit else None
    return products


def rewrite(p, provider, key):
    """Optional LLM rewrite of title + description. Returns (title, body_html)."""
    prompt = (f"Rewrite this ecommerce product for a Shopify store. Return JSON with keys title (max 70 chars) "
              f"and body_html (2 short <p> paragraphs, no invented specs).\nTitle: {p['title']}\nDescription: {p['body_html']}")
    if provider == "OpenAI":
        r = requests.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {key}"},
                          json={"model": "gpt-4o-mini", "response_format": {"type": "json_object"},
                                "messages": [{"role": "user", "content": prompt}]}, timeout=60)
        txt = r.json()["choices"][0]["message"]["content"]
    else:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                          json={"model": "claude-3-5-haiku-latest", "max_tokens": 600,
                                "messages": [{"role": "user", "content": prompt + "\nReply with JSON only."}]}, timeout=60)
        txt = r.json()["content"][0]["text"]
    d = json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    return d.get("title", p["title"]), d.get("body_html", p["body_html"])


def to_shopify_csv(products):
    """Minimal Shopify product import CSV (new products as drafts)."""
    rows = [{"Handle": p["handle"], "Title": p["title"], "Body (HTML)": p["body_html"], "Vendor": "",
             "Type": p["product_type"], "Published": "FALSE", "Option1 Name": "Title",
             "Option1 Value": "Default Title", "Variant Price": f"{p['our_price']:.2f}",
             "Variant Compare At Price": f"{p['price']:.2f}", "Variant Inventory Policy": "deny",
             "Variant Fulfillment Service": "manual", "Image Src": p["image"], "Status": "draft"} for p in products]
    return pd.DataFrame(rows).to_csv(index=False)
