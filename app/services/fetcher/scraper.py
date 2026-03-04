"""Webスクレイピングサービス"""

import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.settings import SelectorConfig
from app.services.fetcher.base import ArticleData, BaseFetcher, FetchError

logger = logging.getLogger(__name__)


class WebScraper(BaseFetcher):
    """Webスクレイピングサービス

    BeautifulSoup4を使用してWebページをスクレイピングし、記事データを取得する
    RSSフィードがないサイトに対応
    """

    def __init__(self, selectors: SelectorConfig, timeout: int = 30):
        """
        Args:
            selectors: スクレイピング用セレクタ設定
            timeout: HTTPリクエストのタイムアウト（秒）
        """
        self.selectors = selectors
        self.timeout = timeout

    async def fetch(self, url: str) -> list[ArticleData]:
        """Webページから記事を取得する

        Args:
            url: スクレイピング対象のURL

        Returns:
            取得した記事リスト

        Raises:
            FetchError: 取得に失敗した場合
        """
        try:
            # HTTPXで非同期リクエスト
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                }
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()
                html = response.text

            # BeautifulSoupで解析
            soup = BeautifulSoup(html, "lxml")

            # 記事リストを取得
            article_elements = soup.select(self.selectors.article_list)
            if not article_elements:
                logger.warning(f"記事リストが見つかりません: {url}")
                return []

            articles = []
            for element in article_elements:
                article = self._parse_article(element, url)
                if article:
                    articles.append(article)

            logger.info(f"Webページから{len(articles)}件の記事を取得: {url}")
            return articles

        except httpx.HTTPError as e:
            raise FetchError(f"HTTPリクエストに失敗: {e}", url, e)
        except Exception as e:
            if isinstance(e, FetchError):
                raise
            raise FetchError(f"Webスクレイピングに失敗: {e}", url, e)

    def _parse_article(self, element, base_url: str) -> Optional[ArticleData]:
        """記事要素を解析して記事データに変換する

        Args:
            element: BeautifulSoupの要素
            base_url: ベースURL（相対URL解決用）

        Returns:
            記事データ（解析失敗時はNone）
        """
        try:
            # タイトル
            title_elem = element.select_one(self.selectors.title)
            if not title_elem:
                return None
            title = title_elem.get_text(strip=True)
            if not title:
                return None

            # リンク
            link_elem = element.select_one(self.selectors.link)
            if not link_elem:
                return None

            # hrefを取得（aタグの場合）
            if link_elem.name == "a":
                href = link_elem.get("href", "")
            else:
                # aタグでない場合は内部のaタグを探す
                a_tag = link_elem.find("a")
                href = a_tag.get("href", "") if a_tag else ""

            if not href:
                return None

            # 相対URLを絶対URLに変換
            url = urljoin(base_url, href)

            # 本文（オプション）
            content = None
            if self.selectors.content:
                content_elem = element.select_one(self.selectors.content)
                if content_elem:
                    content = content_elem.get_text(strip=True)[:2000]

            # 公開日時（オプション）
            published_at = None
            if self.selectors.date:
                date_elem = element.select_one(self.selectors.date)
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    published_at = self._parse_date(date_text)

            return ArticleData(
                title=title,
                url=url,
                content=content,
                published_at=published_at,
            )
        except Exception as e:
            logger.warning(f"記事の解析に失敗: {e}")
            return None

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """日付テキストを解析する

        様々な日付フォーマットに対応
        """
        # 一般的な日付パターン
        patterns = [
            r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",  # 2024-01-15 or 2024/01/15
            r"(\d{4})年(\d{1,2})月(\d{1,2})日",  # 2024年1月15日
        ]

        for pattern in patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    year, month, day = map(int, match.groups())
                    return datetime(year, month, day)
                except ValueError:
                    continue

        return None
