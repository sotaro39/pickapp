"""PickApp - FastAPIアプリケーションエントリーポイント"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import config
from app.core.database import init_db
from app.core.scheduler import scheduler_service
from app.core.settings import load_settings

# ロギング設定
logging.basicConfig(
    level=logging.INFO if config.is_development else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    # 起動時の処理
    logger.info("PickApp starting...")

    # 設定ファイル読み込み
    settings = load_settings()
    logger.info(f"Loaded {len(settings.sources)} sources from config")

    # データベース初期化
    await init_db()
    logger.info("Database initialized")

    # スケジューラ起動
    scheduler_service.start(settings)
    logger.info("Scheduler started")

    yield

    # 終了時の処理
    scheduler_service.shutdown()
    logger.info("Scheduler stopped")
    logger.info("PickApp stopped")


app = FastAPI(
    title="PickApp",
    description="技術ブログ・公式サイトの最新情報をAI要約してLINE/Slackに通知",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """ヘルスチェック用エンドポイント"""
    return {"status": "ok", "app": "PickApp", "version": "1.0.0"}


@app.get("/health")
async def health():
    """ヘルスチェック"""
    return {"status": "healthy"}


@app.post("/api/test/fetch")
async def test_fetch(source_name: str = "Zenn トレンド"):
    """手動でフィード取得→通知をテスト実行"""
    from app.jobs.fetch_job import execute_fetch_job
    
    try:
        await execute_fetch_job(source_name)
        return {"status": "ok", "message": f"ジョブ実行完了: {source_name}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/sources")
async def get_sources():
    """登録されているソース一覧を取得"""
    from app.core.settings import get_settings
    
    settings = get_settings()
    sources = [
        {
            "name": s.name,
            "url": s.url,
            "type": s.type,
            "schedule": s.schedule,
            "keywords": s.keywords,
            "notify": s.notify,
        }
        for s in settings.sources
    ]
    return {"sources": sources}


@app.post("/api/test/slack")
async def test_slack_notification():
    """Slackへの通知テスト（AI要約をスキップ）"""
    from app.core.settings import get_settings
    from app.services.fetcher.rss_fetcher import RSSFetcher
    from app.services.notifier.slack import SlackNotifier
    
    settings = get_settings()
    source = settings.sources[0]  # Zenn トレンド
    
    # Slack設定確認
    if not settings.notifications.slack:
        return {"status": "error", "message": "Slack設定がありません"}
    
    # RSSフィードを取得
    fetcher = RSSFetcher()
    articles = await fetcher.fetch(source.url)
    
    if not articles:
        return {"status": "error", "message": "記事が取得できませんでした"}
    
    # 最初の3記事だけ使用
    articles = articles[:3]
    
    # Slack通知を送信（要約はシンプルなプレースホルダ）
    slack = SlackNotifier(settings.notifications.slack)
    
    message_lines = [f"📰 *{source.name}* の新着記事（テスト）"]
    for a in articles:
        message_lines.append(f"• <{a.url}|{a.title}>")
        message_lines.append(f"  要約: {a.content[:100] if a.content else '内容なし'}...")
    
    message = "\n".join(message_lines)
    result = await slack.send(message)
    
    from app.services.notifier.base import NotificationStatus
    is_success = result.status == NotificationStatus.SUCCESS
    
    return {
        "status": "ok" if is_success else "error",
        "message": f"Slack通知を送信しました（{len(articles)}件）" if is_success else result.error,
        "articles": [{"title": a.title, "url": a.url} for a in articles],
    }


@app.post("/api/test/slack-with-summary")
async def test_slack_with_summary():
    """AI要約付きでSlackへの通知テスト"""
    from app.core.settings import get_settings
    from app.services.fetcher.rss_fetcher import RSSFetcher
    from app.services.notifier.slack import SlackNotifier
    from app.services.summarizer import get_summarizer
    from app.services.notifier.base import NotificationStatus
    
    settings = get_settings()
    source = settings.sources[0]  # Zenn トレンド
    
    # 設定確認
    if not settings.notifications.slack:
        return {"status": "error", "message": "Slack設定がありません"}
    
    # RSSフィードを取得
    fetcher = RSSFetcher()
    articles = await fetcher.fetch(source.url)
    
    if not articles:
        return {"status": "error", "message": "記事が取得できませんでした"}
    
    # 最初の2記事だけ使用（API料金節約）
    articles = articles[:2]
    
    # AI要約を生成
    summarizer = get_summarizer(settings.openai)
    summaries = []
    
    for article in articles:
        try:
            summary = await summarizer.summarize(article.title, article.content or "")
            summaries.append({"title": article.title, "summary": summary, "url": article.url})
        except Exception as e:
            summaries.append({"title": article.title, "summary": f"要約エラー: {str(e)}", "url": article.url})
    
    # Slack通知を送信
    slack = SlackNotifier(settings.notifications.slack)
    
    message_lines = [f"📰 *{source.name}* の新着記事（AI要約テスト）\n"]
    for s in summaries:
        message_lines.append(f"*<{s['url']}|{s['title']}>*")
        message_lines.append(f"📝 {s['summary']}\n")
    
    message = "\n".join(message_lines)
    result = await slack.send(message)
    
    is_success = result.status == NotificationStatus.SUCCESS
    
    return {
        "status": "ok" if is_success else "error",
        "message": f"AI要約付きSlack通知を送信しました（{len(articles)}件）" if is_success else result.error,
        "summaries": summaries,
    }

@app.post("/api/test/line")
async def test_line_notification():
    """LINEへの通知テスト"""
    from app.core.settings import get_settings
    from app.services.notifier.line import LineNotifier
    from app.services.notifier.base import NotificationStatus
    
    settings = get_settings()
    
    # LINE設定確認
    if not settings.notifications.line:
        return {"status": "error", "message": "LINE設定がありません"}
    
    # LINE通知を送信
    line = LineNotifier(settings.notifications.line)
    
    message = "🎉 PickApp LINE通知テスト\n\nこのメッセージが届いていれば、LINE通知は正常に動作しています！"
    result = await line.send(message)
    
    is_success = result.status == NotificationStatus.SUCCESS
    
    return {
        "status": "ok" if is_success else "error",
        "message": "LINE通知を送信しました" if is_success else result.error,
    }


@app.post("/api/test/line-with-summary")
async def test_line_with_summary():
    """AI要約付きでLINEへの通知テスト"""
    from app.core.settings import get_settings
    from app.services.fetcher.rss_fetcher import RSSFetcher
    from app.services.notifier.line import LineNotifier
    from app.services.summarizer import get_summarizer
    from app.services.notifier.base import NotificationStatus
    
    settings = get_settings()
    source = settings.sources[0]  # Zenn トレンド
    
    # 設定確認
    if not settings.notifications.line:
        return {"status": "error", "message": "LINE設定がありません"}
    
    # RSSフィードを取得
    fetcher = RSSFetcher()
    articles = await fetcher.fetch(source.url)
    
    if not articles:
        return {"status": "error", "message": "記事が取得できませんでした"}
    
    # 最初の2記事だけ使用
    articles = articles[:2]
    
    # AI要約を生成
    summarizer = get_summarizer(settings.openai)
    summaries = []
    
    for article in articles:
        try:
            summary = await summarizer.summarize(article.title, article.content or "")
            summaries.append({"title": article.title, "summary": summary, "url": article.url})
        except Exception as e:
            summaries.append({"title": article.title, "summary": f"要約エラー: {str(e)}", "url": article.url})
    
    # LINE通知を送信
    line = LineNotifier(settings.notifications.line)
    
    message_lines = [f"📰 {source.name} の新着記事\n"]
    for s in summaries:
        message_lines.append(f"■ {s['title']}")
        message_lines.append(f"📝 {s['summary']}")
        message_lines.append(f"🔗 {s['url']}\n")
    
    message = "\n".join(message_lines)
    result = await line.send(message)
    
    is_success = result.status == NotificationStatus.SUCCESS
    
    return {
        "status": "ok" if is_success else "error",
        "message": f"AI要約付きLINE通知を送信しました（{len(articles)}件）" if is_success else result.error,
        "summaries": summaries,
    }


@app.post("/api/test/all-sources")
async def test_all_sources():
    """全ソースからAI要約付きでLINE/Slack通知テスト（新フォーマット）"""
    from app.core.settings import get_settings
    from app.services.fetcher.rss_fetcher import RSSFetcher
    from app.services.notifier.slack import SlackNotifier
    from app.services.notifier.line import LineNotifier
    from app.services.summarizer import get_summarizer
    from app.services.notifier.base import NotificationStatus
    
    settings = get_settings()
    fetcher = RSSFetcher()
    summarizer = get_summarizer(settings.openai)
    
    results = []
    
    def get_stars(score: int) -> str:
        """おすすめ度を星に変換"""
        return "★" * score + "☆" * (5 - score)
    
    for source in settings.sources:
        try:
            # 記事取得
            articles = await fetcher.fetch(source.url)
            if not articles:
                results.append({"source": source.name, "status": "no_articles"})
                continue
            
            # 最初の2記事のみ
            articles = articles[:2]
            
            # 英語サイトかどうか
            is_english = source.language == "en"
            
            # AI要約生成（新形式）
            summaries = []
            for article in articles:
                try:
                    result = await summarizer.summarize_with_recommendation(
                        article.title, article.content or "", is_english=is_english
                    )
                    # 英語サイトは日本語訳タイトルを使用
                    display_title = result.title_ja if result.title_ja else article.title
                    summaries.append({
                        "title": display_title,
                        "title_original": article.title if is_english else None,
                        "summary": result.summary,
                        "recommendation": result.recommendation,
                        "recommendation_reason": result.recommendation_reason,
                        "url": article.url
                    })
                except Exception as e:
                    summaries.append({
                        "title": article.title,
                        "title_original": None,
                        "summary": f"要約エラー: {str(e)[:50]}",
                        "recommendation": 3,
                        "recommendation_reason": "評価エラー",
                        "url": article.url
                    })
            
            # Slack通知（新フォーマット）
            if "slack" in source.notify and settings.notifications.slack:
                slack = SlackNotifier(settings.notifications.slack)
                msg_lines = [f"📡 *{source.name}*\n"]
                for s in summaries:
                    msg_lines.append(f"📝 *<{s['url']}|{s['title']}>*\n")
                    msg_lines.append(f"【AI要約】\n{s['summary']}\n")
                    msg_lines.append(f"⭐ 初心者おすすめ度: {get_stars(s['recommendation'])} ({s['recommendation']}/5)")
                    msg_lines.append(f"💡 {s['recommendation_reason']}")
                    msg_lines.append("─" * 20)
                await slack.send("\n".join(msg_lines))
            
            # LINE通知（新フォーマット）
            if "line" in source.notify and settings.notifications.line:
                line = LineNotifier(settings.notifications.line)
                msg_lines = [f"📡 {source.name}\n"]
                for s in summaries:
                    msg_lines.append(f"📝 {s['title']}")
                    msg_lines.append(f"🔗 {s['url']}\n")
                    msg_lines.append(f"【AI要約】\n{s['summary']}\n")
                    msg_lines.append(f"⭐ 初心者おすすめ度: {get_stars(s['recommendation'])} ({s['recommendation']}/5)")
                    msg_lines.append(f"💡 {s['recommendation_reason']}")
                    msg_lines.append("─" * 20)
                await line.send("\n".join(msg_lines))
            
            results.append({
                "source": source.name,
                "status": "ok",
                "articles": len(summaries),
                "notify": source.notify
            })
        except Exception as e:
            results.append({"source": source.name, "status": "error", "error": str(e)[:100]})
    
    return {"results": results}


@app.post("/api/test/save-to-s3")
async def test_save_to_s3():
    """全ソースからAI要約を生成し、S3にテキストファイルとして保存（通知とは別）"""
    from datetime import datetime
    from app.core.settings import get_settings
    from app.services.fetcher.rss_fetcher import RSSFetcher
    from app.services.summarizer import get_summarizer
    
    settings = get_settings()
    
    # S3設定チェック
    if not settings.s3 or not settings.s3.enabled:
        return {"status": "error", "message": "S3設定が無効または未設定です"}
    
    # S3ストレージ初期化
    from app.services.storage.s3_storage import S3Storage
    s3_storage = S3Storage(
        bucket_name=settings.s3.bucket_name,
        aws_access_key_id=settings.s3.aws_access_key_id,
        aws_secret_access_key=settings.s3.aws_secret_access_key,
        aws_region=settings.s3.aws_region,
    )
    
    # 接続確認
    if not s3_storage.check_connection():
        return {"status": "error", "message": "S3バケットに接続できません"}
    
    fetcher = RSSFetcher()
    summarizer = get_summarizer(settings.openai)
    
    results = []
    timestamp = datetime.now()
    article_counter = 0
    
    for source in settings.sources:
        try:
            # 記事取得
            articles = await fetcher.fetch(source.url)
            if not articles:
                results.append({"source": source.name, "status": "no_articles", "saved": []})
                continue
            
            # 最初の2記事のみ
            articles = articles[:2]
            
            # 英語サイトかどうか
            is_english = source.language == "en"
            
            saved_paths = []
            for article in articles:
                article_counter += 1
                try:
                    # AI要約生成
                    summary_result = await summarizer.summarize_with_recommendation(
                        article.title, article.content or "", is_english=is_english
                    )
                    display_title = summary_result.title_ja if summary_result.title_ja else article.title
                    
                    # S3に保存
                    s3_path = await s3_storage.save_article(
                        title=display_title,
                        url=article.url,
                        source_name=source.name,
                        summary=summary_result.summary,
                        recommendation=summary_result.recommendation,
                        recommendation_reason=summary_result.recommendation_reason,
                        article_number=article_counter,
                        published_at=str(article.published_at) if article.published_at else None,
                        timestamp=timestamp,
                    )
                    saved_paths.append(s3_path)
                except Exception as e:
                    saved_paths.append(f"ERROR: {str(e)[:50]}")
            
            results.append({
                "source": source.name,
                "status": "ok",
                "articles": len(articles),
                "saved": saved_paths
            })
        except Exception as e:
            results.append({"source": source.name, "status": "error", "error": str(e)[:100]})
    
    return {
        "status": "ok",
        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "total_articles": article_counter,
        "results": results
    }