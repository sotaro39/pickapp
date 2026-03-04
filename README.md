# PickApp - 技術ブログ通知アプリ

技術ブログや公式サイトの最新情報を取得し、AIで3行要約してLINE/Slackに定時通知するアプリケーションです。

## 機能

- 📰 **RSSフィード対応**: Feedparserで技術ブログのRSSフィードを取得
- 🕷️ **Webスクレイピング対応**: BeautifulSoup4でRSSがないサイトも対応
- 🤖 **AI要約**: OpenAI GPT-4o-miniで記事を3行に要約
- 🔍 **キーワードフィルタリング**: 指定キーワードにマッチする記事のみ通知
- ⏰ **定時通知**: Cron形式でスケジュール設定
- 📱 **LINE/Slack通知**: 複数の通知先に対応
- 🔄 **再送機能**: 通知失敗時は自動リトライ

## 技術スタック

| カテゴリ | 技術 |
|----------|------|
| 言語 | Python 3.11+ |
| フレームワーク | FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| データベース | SQLite (開発) / PostgreSQL (本番) |
| スケジューラ | APScheduler |
| HTTP | HTTPX |
| スクレイピング | BeautifulSoup4 / Feedparser |
| AI | OpenAI SDK |
| コンテナ | Docker / Docker Compose |
| クラウド | AWS (EC2 + RDS) |

## クイックスタート

### 1. 環境変数の設定

```bash
cp .env.example .env
```

`.env` ファイルを編集して、以下の値を設定してください：

```bash
# OpenAI API キー（必須）
OPENAI_API_KEY=sk-xxxxx

# LINE通知を使用する場合
LINE_CHANNEL_ACCESS_TOKEN=xxxxx
LINE_USER_ID=Uxxxxx

# Slack通知を使用する場合
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/xxx/xxx
```

### 2. ソース設定

`config/sources.yaml` を編集して、監視するサイトを設定します：

```yaml
sources:
  - name: "Zenn トレンド"
    url: "https://zenn.dev/feed"
    type: rss
    schedule: "0 9 * * *"  # 毎日9時
    keywords:
      - Python
      - FastAPI
    notify:
      - line
      - slack
```

### 3. 起動

#### Docker使用（推奨）

```bash
# 開発環境
docker-compose up -d

# ログ確認
docker-compose logs -f
```

#### ローカル実行

```bash
# 仮想環境作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存パッケージインストール
pip install -r requirements.txt

# 起動
uvicorn app.main:app --reload
```

### 4. 動作確認

```bash
# ヘルスチェック
curl http://localhost:8000/health
```

## 設定ファイル

### sources.yaml

```yaml
sources:
  # RSSフィード対応サイト
  - name: "サイト名"
    url: "https://example.com/feed"
    type: rss
    schedule: "0 9 * * *"  # Cron形式
    keywords: [Python, AWS]  # フィルタリング（空でフィルタなし）
    notify: [line, slack]  # 通知先

  # Webスクレイピング対応サイト（RSSなし）
  - name: "技術ブログX"
    url: "https://example.com/blog"
    type: scrape
    schedule: "0 12 * * *"
    selectors:
      article_list: "div.post-list > article"
      title: "h2.title"
      link: "a.read-more"
      date: "span.date"
      content: "p.summary"
    keywords: []
    notify: [line]

notifications:
  line:
    channel_access_token: "${LINE_CHANNEL_ACCESS_TOKEN}"
    user_id: "${LINE_USER_ID}"
  slack:
    webhook_url: "${SLACK_WEBHOOK_URL}"

openai:
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-4o-mini"
```

### スケジュール形式（Cron）

```
# 分 時 日 月 曜日
0 9 * * *     # 毎日9時
0 9,18 * * *  # 毎日9時と18時
0 9 * * 1-5   # 平日9時
*/30 * * * *  # 30分ごと
```

## プロジェクト構造

```
pickapp/
├── app/
│   ├── main.py              # FastAPIエントリーポイント
│   ├── core/
│   │   ├── config.py        # 環境変数設定
│   │   ├── settings.py      # YAML設定読み込み
│   │   ├── database.py      # DB接続
│   │   └── scheduler.py     # スケジューラ
│   ├── models/
│   │   ├── article.py       # 記事モデル
│   │   └── retry_queue.py   # 再送キュー
│   ├── services/
│   │   ├── fetcher/         # 記事取得
│   │   ├── notifier/        # 通知送信
│   │   ├── summarizer.py    # AI要約
│   │   └── filter.py        # キーワードフィルタ
│   └── jobs/
│       └── fetch_job.py     # 定期実行ジョブ
├── config/
│   └── sources.yaml         # ソース設定
├── docker/
│   ├── Dockerfile
│   └── Dockerfile.dev
├── docker-compose.yml       # 開発用
├── docker-compose.prod.yml  # 本番用
└── requirements.txt
```

## AWS デプロイ

詳細は [docs/aws-deployment.md](docs/aws-deployment.md) を参照してください。

### 必要なAWSリソース

- **EC2** (Amazon Linux 2023): アプリケーションサーバー
- **RDS** (PostgreSQL 15): データベース
- **VPC**: ネットワーク
- **Security Group**: ファイアウォール

## 通知メッセージ例

### 記事通知
```
📰 Zenn トレンド - 新着記事

【FastAPI 2.0の新機能まとめ】

・FastAPI 2.0で非同期処理が大幅に改善
・Pydantic v2統合によりバリデーション速度が向上
・新しいLifespanイベントハンドラが追加

🔗 https://zenn.dev/example/articles/fastapi-2
```

### 新着なし通知
```
ℹ️ Zenn トレンド
最新の情報はありませんでした
```

### エラー通知
```
❌ Zenn トレンド
取得に失敗しました

エラー: HTTPリクエストに失敗: Connection timeout
```

## ライセンス

MIT License