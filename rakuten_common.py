"""
楽天API呼び出しとAIキャプション生成の共通処理。
generate_content.py から使われる。
"""

import os
import random
import requests

RAKUTEN_APP_ID = os.environ["RAKUTEN_APP_ID"]
RAKUTEN_ACCESS_KEY = os.environ["RAKUTEN_ACCESS_KEY"]
RAKUTEN_AFFILIATE_ID = os.environ["RAKUTEN_AFFILIATE_ID"]
RAKUTEN_SITE_URL = os.environ["RAKUTEN_SITE_URL"].rstrip("/") + "/"
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

RAKUTEN_GENRE_ID = os.environ.get("RAKUTEN_GENRE_ID", "0")
RAKUTEN_KEYWORD = os.environ.get("RAKUTEN_KEYWORD", "")

RAKUTEN_HEADERS = {
    "Referer": RAKUTEN_SITE_URL,
    "Origin": RAKUTEN_SITE_URL.rstrip("/"),
}


def fetch_top_product():
    """楽天ランキングAPI(キーワードがあれば商品検索API)から商品を1件取得する"""
    if RAKUTEN_KEYWORD:
        url = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
        params = {
            "format": "json",
            "applicationId": RAKUTEN_APP_ID,
            "accessKey": RAKUTEN_ACCESS_KEY,
            "affiliateId": RAKUTEN_AFFILIATE_ID,
            "keyword": RAKUTEN_KEYWORD,
            "sort": "-reviewCount",
            "hits": 5,
        }
    else:
        url = "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"
        params = {
            "format": "json",
            "applicationId": RAKUTEN_APP_ID,
            "accessKey": RAKUTEN_ACCESS_KEY,
            "affiliateId": RAKUTEN_AFFILIATE_ID,
            "genreId": RAKUTEN_GENRE_ID,
            "period": "realtime",
        }

    resp = requests.get(url, params=params, headers=RAKUTEN_HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    items = data.get("Items", [])
    if not items:
        raise RuntimeError(f"楽天APIから商品が取得できませんでした: {data}")

    item = random.choice(items)["Item"]

    image_url = None
    if item.get("mediumImageUrls"):
        image_url = item["mediumImageUrls"][0]["imageUrl"].split("?")[0]

    return {
        "name": item["itemName"],
        "price": item["itemPrice"],
        "url": item.get("affiliateUrl") or item["itemUrl"],
        "image_url": image_url,
        "shop": item.get("shopName", ""),
    }


def generate_caption(product):
    """Anthropic APIでInstagram投稿用キャプションを生成する"""
    prompt = f"""以下の楽天市場の商品情報をもとに、Instagramのリール投稿用キャプションを1つ作成してください。

商品名: {product['name']}
価格: {product['price']}円
ショップ: {product['shop']}

条件:
- 絵文字を適度に使い、親しみやすい雰囲気にする
- 3〜5行程度で簡潔にする
- 最後に「プロフィールのリンクから商品ページをチェックしてね」という一文を入れる
- 最後に関連ハッシュタグを5個ほどつける(#は半角)
- キャプション本文だけを出力し、前置きや説明は書かない
"""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-5",
            "max_tokens": 500,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    if not resp.ok:
        print(f"Anthropic APIエラー詳細: {resp.status_code} {resp.text}")
    resp.raise_for_status()
    data = resp.json()
    return "".join(
        block["text"] for block in data["content"] if block["type"] == "text"
    ).strip()
