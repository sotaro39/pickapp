"""記事取得ジョブ

スケジューラによって定期実行される記事取得・通知ジョブ
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.settings import AppSettings, SourceConfig, get_settings
from app.models.article import Article
from app.services.fetcher.base import ArticleData, BaseFetcher, FetchError
from app.services.fetcher.rss_fetcher import RSSFetcher
from app.services.fetcher.scraper import WebScraper
from app.services.filter import create_filter
from app.services.notifier.base import NotificationStatus
from app.services.notifier.line import LineNotifier
from app.services.notifier.slack import SlackNotifier
from app.services.retry_queue import RetryQueueService
from app.services.summarizer import get_summarizer

logger = logging.getLogger(__name__)


async def execute_fetch_job(source_name: str) -> None:
    """記事取得ジョブを実行する

    Args:
        source_name: ソース名
    """
    logger.info(f"ジョブ開始: {source_name}")

    try:
        settings = get_settings()

        # ソース設定を取得
        source = _get_source_config(settings, source_name)
        if not source:
            logger.error(f"ソース設定が見つかりません: {source_name}")
            return

        async with AsyncSessionLocal() as db:
            await _process_source(db, settings, source)

    except Exception as e:
        logger.error(f"ジョブエラー: {source_name} - {e}")
        # エラー通知を送信
        await _send_error_notification(source_name, str(e))

    logger.info(f"ジョブ完了: {source_name}")


def _get_source_config(settings: AppSettings, source_name: str) -> Optional[SourceConfig]:
    """ソース設定を取得する"""
    for source in settings.sources:
        if source.name == source_name:
            return source
    return None


def _create_fetcher(source: SourceConfig) -> BaseFetcher:
    """ソースタイプに応じたFetcherを作成する"""
    if source.type == "rss":
        return RSSFetcher()
    elif source.type == "scrape":
        if not source.selectors:
            raise ValueError(f"スクレイピング設定にselectorsが必要です: {source.name}")
        return WebScraper(source.selectors)
    else:
        raise ValueError(f"未対応のソースタイプ: {source.type}")


async def _process_source(
    db: AsyncSession,
    settings: AppSettings,
    source: SourceConfig,
) -> None:
    """ソースを処理する（記事取得→フィルタ→要約→通知）"""
    try:
        # 1. 記事を取得
        fetcher = _create_fetcher(source)
        articles = await fetcher.fetch(source.url)
        logger.info(f"取得記事数: {len(articles)} ({source.name})")

        if not articles:
            # 記事がない場合は通知
            await _send_no_data_notification(settings, source)
            return

        # 2. 重複除去（既に取得済みの記事を除外）
        new_articles = await _filter_existing_articles(db, articles, source.name)
        logger.info(f"新規記事数: {len(new_articles)} ({source.name})")

        if not new_articles:
            await _send_no_data_notification(settings, source)
            return

        # 3. キーワードフィルタリング
        filter_service = create_filter(source.keywords)
        filtered_articles = filter_service.filter_articles(new_articles)
        logger.info(f"フィルタ後記事数: {len(filtered_articles)} ({source.name})")

        if not filtered_articles:
            await _send_no_data_notification(settings, source)
            return

        # 4. 各記事を処理（要約→通知→DB保存）
        summarizer = get_summarizer(settings.openai)

        for article in filtered_articles:
            await _process_article(db, settings, source, article, summarizer)

    except FetchError as e:
        logger.error(f"取得エラー: {source.name} - {e}")
        await _send_error_notification_with_settings(settings, source, str(e))


async def _filter_existing_articles(
    db: AsyncSession,
    articles: list[ArticleData],
    source_name: str,
) -> list[ArticleData]:
    """既存の記事を除外する"""
    # 記事URLのリスト
    urls = [a.url for a in articles]

    # 既存の記事を取得
    stmt = select(Article.url).where(Article.url.in_(urls))
    result = await db.execute(stmt)
    existing_urls = set(row[0] for row in result)

    # 新規記事のみ返す
    return [a for a in articles if a.url not in existing_urls]


async def _process_article(
    db: AsyncSession,
    settings: AppSettings,
    source: SourceConfig,
    article: ArticleData,
    summarizer,
) -> None:
    """個別の記事を処理する"""
    try:
        # AI要約を生成
        summary = await summarizer.summarize(article.title, article.content)
        logger.debug(f"要約生成完了: {article.title[:30]}...")

        # 通知を送信
        await _send_article_notification(settings, source, article, summary)

        # DBに保存（重複防止用）
        db_article = Article(
            source_name=source.name,
            url=article.url,
            title=article.title,
            content=article.content[:2000] if article.content else None,
            summary=summary,
            is_notified=True,
            notified_at=datetime.utcnow(),
            published_at=article.published_at,
        )
        db.add(db_article)
        await db.commit()

    except Exception as e:
        logger.error(f"記事処理エラー: {article.title[:30]} - {e}")
        # 記事単位のエラーは続行


async def _send_article_notification(
    settings: AppSettings,
    source: SourceConfig,
    article: ArticleData,
    summary: str,
) -> None:
    """記事通知を送信する"""
    for notify_type in source.notify:
        try:
            if notify_type == "line" and settings.notifications.line:
                notifier = LineNotifier(settings.notifications.line)
                message = notifier.format_article_message(
                    source.name, article.title, article.url, summary
                )
                result = await notifier.send(message)
                if result.status != NotificationStatus.SUCCESS:
                    await _enqueue_retry(settings, notify_type, message, source.name)

            elif notify_type == "slack" and settings.notifications.slack:
                notifier = SlackNotifier(settings.notifications.slack)
                message = notifier.format_article_message(
                    source.name, article.title, article.url, summary
                )
                result = await notifier.send(message)
                if result.status != NotificationStatus.SUCCESS:
                    await _enqueue_retry(settings, notify_type, message, source.name)

        except Exception as e:
            logger.error(f"通知送信エラー ({notify_type}): {e}")
            # 再送キューに追加
            message = f"📰 {source.name}\n{article.title}\n{summary}\n{article.url}"
            await _enqueue_retry(settings, notify_type, message, source.name, str(e))


async def _send_no_data_notification(
    settings: AppSettings,
    source: SourceConfig,
) -> None:
    """新着なし通知を送信する"""
    for notify_type in source.notify:
        try:
            if notify_type == "line" and settings.notifications.line:
                notifier = LineNotifier(settings.notifications.line)
                await notifier.send_no_data(source.name)

            elif notify_type == "slack" and settings.notifications.slack:
                notifier = SlackNotifier(settings.notifications.slack)
                await notifier.send_no_data(source.name)

        except Exception as e:
            logger.error(f"新着なし通知送信エラー ({notify_type}): {e}")


async def _send_error_notification(source_name: str, error: str) -> None:
    """エラー通知を送信する（設定なし版）"""
    try:
        settings = get_settings()
        source = _get_source_config(settings, source_name)
        if source:
            await _send_error_notification_with_settings(settings, source, error)
    except Exception as e:
        logger.error(f"エラー通知送信失敗: {e}")


async def _send_error_notification_with_settings(
    settings: AppSettings,
    source: SourceConfig,
    error: str,
) -> None:
    """エラー通知を送信する"""
    for notify_type in source.notify:
        try:
            if notify_type == "line" and settings.notifications.line:
                notifier = LineNotifier(settings.notifications.line)
                await notifier.send_error(source.name, error)

            elif notify_type == "slack" and settings.notifications.slack:
                notifier = SlackNotifier(settings.notifications.slack)
                await notifier.send_error(source.name, error)

        except Exception as e:
            logger.error(f"エラー通知送信エラー ({notify_type}): {e}")


async def _enqueue_retry(
    settings: AppSettings,
    notification_type: str,
    message: str,
    source_name: str,
    error: Optional[str] = None,
) -> None:
    """再送キューに追加する"""
    try:
        retry_service = RetryQueueService(settings)
        async with AsyncSessionLocal() as db:
            await retry_service.enqueue(
                db, notification_type, message, source_name, error
            )
    except Exception as e:
        logger.error(f"再送キュー追加エラー: {e}")
