"""キーワードフィルタリングサービス"""

import logging
import re
from typing import Optional

from app.services.fetcher.base import ArticleData

logger = logging.getLogger(__name__)


class FilterService:
    """キーワードによる記事フィルタリングサービス

    指定されたキーワードにマッチする記事のみを抽出する
    """

    def __init__(self, keywords: list[str]):
        """
        Args:
            keywords: フィルタリング用キーワードリスト（空の場合はフィルタなし）
        """
        self.keywords = keywords
        # キーワードを小文字に正規化（大文字小文字を区別しない）
        self.normalized_keywords = [k.lower() for k in keywords]

    def filter_articles(self, articles: list[ArticleData]) -> list[ArticleData]:
        """記事リストをキーワードでフィルタリングする

        Args:
            articles: フィルタリング対象の記事リスト

        Returns:
            キーワードにマッチした記事リスト
        """
        # キーワードが空の場合は全件返す
        if not self.keywords:
            logger.debug("キーワード未設定のため、全件を対象とします")
            return articles

        filtered = []
        for article in articles:
            if self._matches_keywords(article):
                filtered.append(article)

        logger.info(
            f"フィルタリング結果: {len(filtered)}/{len(articles)}件がマッチ "
            f"(キーワード: {', '.join(self.keywords)})"
        )
        return filtered

    def _matches_keywords(self, article: ArticleData) -> bool:
        """記事がキーワードにマッチするか判定する

        Args:
            article: 判定対象の記事

        Returns:
            いずれかのキーワードにマッチすればTrue
        """
        # 検索対象テキストを作成（タイトル + 本文）
        search_text = self._normalize_text(article.title)
        if article.content:
            search_text += " " + self._normalize_text(article.content)

        # いずれかのキーワードにマッチするか
        for keyword in self.normalized_keywords:
            if self._keyword_matches(keyword, search_text):
                logger.debug(f"キーワード '{keyword}' がマッチ: {article.title[:50]}")
                return True

        return False

    def _normalize_text(self, text: str) -> str:
        """テキストを正規化する（小文字化、空白正規化）"""
        # 小文字化
        text = text.lower()
        # 連続する空白を単一スペースに
        text = re.sub(r"\s+", " ", text)
        return text

    def _keyword_matches(self, keyword: str, text: str) -> bool:
        """キーワードがテキストにマッチするか判定する

        単語境界を考慮したマッチングを行う
        """
        # 英数字のキーワードは単語境界を考慮
        if keyword.isascii() and keyword.replace("-", "").replace("_", "").isalnum():
            # 単語境界を考慮したパターン
            pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
            return bool(re.search(pattern, text, re.IGNORECASE))
        else:
            # 日本語などは単純な部分一致
            return keyword in text


def create_filter(keywords: Optional[list[str]] = None) -> FilterService:
    """フィルタサービスを作成する

    Args:
        keywords: キーワードリスト（Noneまたは空の場合はフィルタなし）

    Returns:
        FilterService インスタンス
    """
    return FilterService(keywords or [])
