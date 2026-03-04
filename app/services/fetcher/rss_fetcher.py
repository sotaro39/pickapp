"""RSSフィード取得サービス"""

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx

from app.services.fetcher.base import ArticleData, BaseFetcher, FetchError

logger = logging.getLogger(__name__)


class RSSFetcher(BaseFetcher):
    """RSSフィード取得サービス

    Feedparserを使用してRSSフィードを解析し、記事データを取得する
    """

    def __init__(self, timeout: int = 30):
        """
        Args:
            timeout: HTTPリクエストのタイムアウト（秒）
        """
        self.timeout = timeout

    async def fetch(self, url: str) -> list[ArticleData]:
        """RSSフィードから記事を取得する

        Args:
            url: RSSフィードのURL

        Returns:
            取得した記事リスト

        Raises:
            FetchError: 取得に失敗した場合
        """
        try:
            # HTTPXで非同期リクエスト
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()
                content = response.text

            # Feedparserで解析
            feed = feedparser.parse(content)

            if feed.bozo and not feed.entries:
                raise FetchError(
                    f"RSSフィードの解析に失敗: {feed.bozo_exception}",
                    url,
                    feed.bozo_exception,
                )

            articles = []
            for entry in feed.entries:
                article = self._parse_entry(entry, url)
                if article:
                    articles.append(article)

            logger.info(f"RSSフィードから{len(articles)}件の記事を取得: {url}")
            return articles

        except httpx.HTTPError as e:
            raise FetchError(f"HTTPリクエストに失敗: {e}", url, e)
        except Exception as e:
            if isinstance(e, FetchError):
                raise
            raise FetchError(f"RSSフィードの取得に失敗: {e}", url, e)

    def _parse_entry(self, entry: dict, feed_url: str) -> Optional[ArticleData]:
        """フィードエントリを解析して記事データに変換する

        Args:
            entry: Feedparserのエントリ
            feed_url: フィードURL

        Returns:
            記事データ（解析失敗時はNone）
        """
        try:
            # タイトル
            title = entry.get("title", "").strip()
            if not title:
                return None

            # URL
            url = entry.get("link", "").strip()
            if not url:
                return None

            # 本文（サマリーまたはコンテンツ）
            content = None
            if "summary" in entry:
                content = entry.summary
            elif "content" in entry and entry.content:
                content = entry.content[0].get("value", "")

            # HTMLタグを簡易的に除去
            if content:
                import re
                content = re.sub(r"<[^>]+>", "", content)
                content = content.strip()[:2000]  # 最大2000文字

            # 公開日時
            published_at = self._parse_date(entry)

            return ArticleData(
                title=title,
                url=url,
                content=content,
                published_at=published_at,
            )
        except Exception as e:
            logger.warning(f"エントリの解析に失敗: {e}")
            return None

    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """エントリから公開日時を解析する"""
        for date_field in ["published", "updated", "created"]:
            if date_field in entry:
                try:
                    return parsedate_to_datetime(entry[date_field])
                except (ValueError, TypeError):
                    pass

            parsed_field = f"{date_field}_parsed"
            if parsed_field in entry and entry[parsed_field]:
                try:
                    return datetime(*entry[parsed_field][:6])
                except (ValueError, TypeError):
                    pass

        return None
