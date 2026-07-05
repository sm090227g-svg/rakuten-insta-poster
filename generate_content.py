"""
① 楽天商品を取得
② AIでキャプションを生成
③ 商品画像+商品名+価格を1枚のカード画像に合成
④ カード画像をFFmpegでゆっくりズームする動画にする
⑤ 次のステップ(publish_reel.py)が使う情報を run_state.json に保存する

このスクリプトはInstagramへの投稿は行わない。
動画をGitHubにpushして公開URLが出来た後、publish_reel.pyが投稿を担当する。
"""

import glob
import io
import json
import subprocess
import textwrap

import requests
from PIL import Image, ImageDraw, ImageFont

from rakuten_common import fetch_top_product, generate_caption

W, H = 1080, 1920
BG_COLOR = (247, 247, 247)
RED = (191, 0, 0)


def find_japanese_font(bold=True):
    """日本語対応フォント(Noto Sans CJK)を探す"""
    candidates = glob.glob("/usr/share/fonts/**/*NotoSansCJK*", recursive=True)
    if not candidates:
        return None
    bold_matches = [c for c in candidates if "Bold" in c]
    if bold and bold_matches:
        return bold_matches[0]
    non_bold = [c for c in candidates if "Bold" not in c]
    return non_bold[0] if non_bold else candidates[0]


def load_font(path, size):
    if path is None:
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(path, size, index=0)
    except Exception:
        return ImageFont.load_default()


def compose_card_image(product, out_path="docs/reel-card.png"):
    """商品画像+商品名+価格を1枚のカード画像に合成する"""
    canvas = Image.new("RGB", (W, H), BG_COLOR)

    resp = requests.get(product["image_url"], timeout=15)
    resp.raise_for_status()
    photo = Image.open(io.BytesIO(resp.content)).convert("RGB")
    side = min(photo.size)
    left = (photo.width - side) // 2
    top = (photo.height - side) // 2
    photo = photo.crop((left, top, left + side, top + side)).resize((W, W))
    canvas.paste(photo, (0, 0))

    draw = ImageDraw.Draw(canvas)
    bold_path = find_japanese_font(bold=True)
    regular_path = find_japanese_font(bold=False)

    badge_font = load_font(bold_path, 42)
    name_font = load_font(bold_path, 52)
    price_font = load_font(bold_path, 84)
    hint_font = load_font(regular_path, 38)

    y = W + 70

    draw.rounded_rectangle((60, y, 400, y + 80), radius=40, fill=RED)
    draw.text((90, y + 16), "本日のおすすめ", font=badge_font, fill="white")
    y += 140

    wrapped = textwrap.wrap(product["name"], width=18)[:4]
    for line in wrapped:
        draw.text((60, y), line, font=name_font, fill=(30, 30, 30))
        y += 70

    y += 30
    draw.text((60, y), f"{product['price']:,}円", font=price_font, fill=RED)
    y += 140

    draw.text(
        (60, y),
        "→ プロフィールのリンクからチェック",
        font=hint_font,
        fill=(120, 120, 120),
    )

    canvas.save(out_path)
    return out_path


def create_reel_video(image_path, out_path="docs/reel-video.mp4", duration=6, fps=25):
    """静止画にゆっくりズームする動きをつけて動画化する(Ken Burns効果)"""
    frames = duration * fps
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-vf",
        f"zoompan=z='min(zoom+0.0015,1.15)':d={frames}:s={W}x{H}:fps={fps}",
        "-t", str(duration),
        "-shortest",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-movflags", "+faststart",
        out_path,
    ]
    subprocess.run(cmd, check=True)
    return out_path


def main():
    print("① 楽天商品を取得中...")
    product = fetch_top_product()
    print(f"   → {product['name']} ({product['price']}円)")

    if not product["image_url"]:
        raise RuntimeError("画像URLが取得できませんでした。")

    print("② キャプションを生成中...")
    caption = generate_caption(product)
    print(f"   → {caption[:60]}...")

    print("③ カード画像を合成中...")
    card_path = compose_card_image(product)

    print("④ リール動画を作成中...")
    video_path = create_reel_video(card_path)
    print(f"   → {video_path} を作成しました")

    with open("run_state.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "product": product,
                "caption": caption,
                "video_file": "reel-video.mp4",
            },
            f,
            ensure_ascii=False,
        )
    print("⑤ run_state.json を保存しました")


if __name__ == "__main__":
    main()
