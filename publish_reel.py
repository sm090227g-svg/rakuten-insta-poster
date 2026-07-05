"""
generate_content.py で作った動画を、GitHubにpushして公開URLが出来た後に
Instagramへリールとして投稿する。

必要な環境変数:
  IG_ACCESS_TOKEN
  IG_USER_ID
  GITHUB_REPOSITORY  (GitHub Actions上では自動的に設定される)
  VIDEO_COMMIT_SHA   (動画をpushしたコミットのSHA。ワークフロー側で設定する)
"""

import datetime
import json
import os
import sys
import time

import requests

IG_ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]
IG_USER_ID = os.environ["IG_USER_ID"]
GRAPH_API_VERSION = "v21.0"


def post_reel_to_instagram(video_url, caption):
    """Instagram Graph APIでリール動画を投稿する"""
    base = f"https://graph.instagram.com/{GRAPH_API_VERSION}/{IG_USER_ID}"

    create_resp = requests.post(
        f"{base}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": IG_ACCESS_TOKEN,
        },
        timeout=30,
    )
    if not create_resp.ok:
        print(f"Instagram(メディア作成)エラー詳細: {create_resp.status_code} {create_resp.text}", file=sys.stderr)
    create_resp.raise_for_status()
    creation_id = create_resp.json()["id"]

    # 動画の処理が終わるまで待つ(最大2分)
    for _ in range(24):
        time.sleep(5)
        status_resp = requests.get(
            f"https://graph.instagram.com/{GRAPH_API_VERSION}/{creation_id}",
            params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN},
            timeout=30,
        )
        status = status_resp.json().get("status_code")
        print(f"   動画処理状況: {status}")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError("Instagram側で動画の処理に失敗しました。")
    else:
        raise RuntimeError("動画の処理がタイムアウトしました。")

    publish_resp = requests.post(
        f"{base}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": IG_ACCESS_TOKEN,
        },
        timeout=30,
    )
    if not publish_resp.ok:
        print(f"Instagram(公開)エラー詳細: {publish_resp.status_code} {publish_resp.text}", file=sys.stderr)
    publish_resp.raise_for_status()
    return publish_resp.json()


def update_landing_page(product):
    """『今日のおすすめ』ページ用のJSONファイルを書き換える"""
    data = {
        "name": product["name"],
        "price": product["price"],
        "image_url": product["image_url"],
        "url": product["url"],
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    with open("docs/product-data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    with open("run_state.json", encoding="utf-8") as f:
        state = json.load(f)

    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["VIDEO_COMMIT_SHA"]
    video_url = f"https://raw.githubusercontent.com/{repo}/{sha}/docs/{state['video_file']}"

    print(f"① Instagramにリール動画を投稿中...\n   動画URL: {video_url}")
    result = post_reel_to_instagram(video_url, state["caption"])
    print(f"   → 投稿完了 (media id: {result.get('id')})")

    print("② ランディングページを更新中...")
    update_landing_page(state["product"])
    print("   → docs/product-data.json を更新しました")


if __name__ == "__main__":
    main()
