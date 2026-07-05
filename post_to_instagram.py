"""
楽天ランキング上位商品を取得 → Claudeでキャプション生成 → Instagramに自動投稿する

必要な環境変数(GitHub Secretsに登録):
  RAKUTEN_APP_ID       楽天アプリケーションID
  RAKUTEN_ACCESS_KEY   楽天アクセスキー(2026年2月の仕様変更で追加された必須項目)
  RAKUTEN_AFFILIATE_ID 楽天アフィリエイトID
  RAKUTEN_SITE_URL     楽天アプリ登録時に「許可されたウェブサイト」に登録したURL
                       (例: https://sm090227g-svg.github.io/insta-rakuten-app/)
  IG_ACCESS_TOKEN      Instagram長期アクセストークン
  IG_USER_ID           InstagramビジネスアカウントID
  ANTHROPIC_API_KEY    Anthropic APIキー(キャプション生成用)

任意で指定できる環境変数:
  RAKUTEN_GENRE_ID     楽天ジャンルID(未指定なら総合ランキング)
  RAKUTEN_KEYWORD      キーワード検索したい場合に指定(例: 外壁 塗装)

【2026年2月の楽天API仕様変更について】
楽天ウェブサービスは2026年2月に旧ドメイン(app.rakuten.co.jp)を廃止し、
新ドメイン(openapi.rakuten.co.jp)に完全移行しました。
新APIでは applicationId に加えて accessKey が必須になり、さらに
アプリ登録時に「許可されたウェブサイト」として登録したドメインを
Referer/Originヘッダーとして送る必要があります。
"""

import os
import sys
import time
import requests

RAKUTEN_APP_ID = os.environ["RAKUTEN_APP_ID"]
RAKUTEN_ACCESS_KEY = os.environ["RAKUTEN_ACCESS_KEY"]
RAKUTEN_AFFILIATE_ID = os.environ["RAKUTEN_AFFILIATE_ID"]
RAKUTEN_SITE_URL = os.environ["RAKUTEN_SITE_URL"].rstrip("/") + "/"
IG_ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]
IG_USER_ID = os.environ["IG_USER_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

RAKUTEN_GENRE_ID = os.environ.get("RAKUTEN_GENRE_ID", "0")
RAKUTEN_KEYWORD = os.environ.get("RAKUTEN_KEYWORD", "")

GRAPH_API_VERSION = "v21.0"

# 楽天の新API(2026年2月以降)は、アプリ登録時に許可したサイトからのアクセスである
# ことをReferer/Originヘッダーで確認するため、これを送る
RAKUTEN_HEADERS = {
    "Referer": RAKUTEN_SITE_URL,
    "Origin": RAKUTEN_SITE_URL.rstrip("/"),
}


def fetch_top_product():
    """楽天ランキングAPI(キーワードがあれば商品検索API)から商品を1件取得する"""
    if RAKUTEN_KEYWORD:
        # キーワード検索(人気順)
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
        # 総合(またはジャンル指定)ランキング
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

    # 直近で投稿していない商品を選ぶ(簡易的に毎回リストの中からランダム性を持たせる)
    import random

    item = random.choice(items)["Item"]

    image_url = None
    if item.get("mediumImageUrls"):
        image_url = item["mediumImageUrls"][0]["imageUrl"]
        # サイズ指定を外して高解像度を狙う(?_ex=128x128 のようなクエリを削除)
        image_url = image_url.split("?")[0]

    return {
        "name": item["itemName"],
        "price": item["itemPrice"],
        "url": item.get("affiliateUrl") or item["itemUrl"],
        "image_url": image_url,
        "shop": item.get("shopName", ""),
    }


def generate_caption(product):
    """Anthropic APIでInstagram投稿用キャプションを生成する"""
    prompt = f"""以下の楽天市場の商品情報をもとに、Instagramの投稿キャプションを1つ作成してください。

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
    resp.raise_for_status()
    data = resp.json()
    caption = "".join(
        block["text"] for block in data["content"] if block["type"] == "text"
    ).strip()
    return caption


def post_to_instagram(image_url, caption):
    """Instagram Graph APIで画像投稿を作成→公開する"""
    base = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{IG_USER_ID}"

    # ① メディアコンテナを作成
    create_resp = requests.post(
        f"{base}/media",
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": IG_ACCESS_TOKEN,
        },
        timeout=30,
    )
    create_resp.raise_for_status()
    creation_id = create_resp.json()["id"]

    # ② 処理が終わるまで少し待つ(画像は通常すぐ終わる)
    time.sleep(5)

    # ③ 公開
    publish_resp = requests.post(
        f"{base}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": IG_ACCESS_TOKEN,
        },
        timeout=30,
    )
    publish_resp.raise_for_status()
    return publish_resp.json()


def main():
    print("① 楽天商品を取得中...")
    product = fetch_top_product()
    print(f"   → {product['name']} ({product['price']}円)")

    if not product["image_url"]:
        print("画像URLが取得できなかったため終了します。", file=sys.stderr)
        sys.exit(1)

    print("② キャプションを生成中...")
    caption = generate_caption(product)
    print(f"   → {caption[:60]}...")

    print("③ Instagramに投稿中...")
    result = post_to_instagram(product["image_url"], caption)
    print(f"   → 投稿完了 (media id: {result.get('id')})")


if __name__ == "__main__":
    main()
