# 楽天商品 Instagram 自動投稿

楽天ランキング上位の商品を取得し、AIでキャプションを作って、毎日自動でInstagramに投稿する仕組みです。

## セットアップ手順

### ① このフォルダをGitHubリポジトリにアップロードする

新しいリポジトリ(Publicで構いません)を作り、この中の全ファイル・フォルダをアップロードしてください。
`.github/workflows/daily-post.yml` も含めて、フォルダ構造を保ったままアップロードすることが重要です。

### ② GitHub Secretsに5つのキーを登録する

1. リポジトリの「Settings」タブを開く
2. 左メニューの「Secrets and variables」→「Actions」
3. 「New repository secret」で以下を1つずつ登録する

| Secret名 | 値 |
|---|---|
| `RAKUTEN_APP_ID` | 楽天のアプリケーションID |
| `RAKUTEN_AFFILIATE_ID` | 楽天のアフィリエイトID |
| `IG_ACCESS_TOKEN` | Instagramの長期アクセストークン |
| `IG_USER_ID` | InstagramビジネスアカウントのユーザーID |
| `ANTHROPIC_API_KEY` | Anthropic APIキー(https://console.anthropic.com で発行) |

### ③ 動作確認する

1. リポジトリの「Actions」タブを開く
2. 左側の「楽天商品Instagram自動投稿」をクリック
3. 右側の「Run workflow」ボタンで手動実行してみる
4. 数十秒〜1分ほどで、Instagramに投稿されるか確認する

うまくいけば、**毎日19:00(日本時間)に自動で投稿されるようになります。**

## カスタマイズ

- 投稿時間を変えたい場合は `.github/workflows/daily-post.yml` の `cron` の時間を変更してください(UTC表記です)
- 特定ジャンルの商品だけ投稿したい場合は、Secretsに `RAKUTEN_GENRE_ID` を追加してください(楽天のジャンルID一覧から選びます)
- キーワードで検索したい場合(例:外壁・外装関連グッズ)は、Secretsに `RAKUTEN_KEYWORD` を追加してください(例:`外壁 塗装`)

## 注意点

- `IG_ACCESS_TOKEN` は発行から60日で期限切れになります。切れる前に再発行してSecretsを更新してください。
- Anthropic APIは有料ですが、1日1回のキャプション生成程度であれば費用はごくわずかです。
