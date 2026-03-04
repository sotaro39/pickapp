"""記事取得サービスの抽象基底クラス"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ArticleData:
    """取得した記事データ"""

    title: str
    url: str
    content: Optional[str] = None
    published_at: Optional[datetime] = None

    def __repr__(self) -> str:
        return f"<ArticleData(title='{self.title[:30]}...', url='{self.url}')>"


class BaseFetcher(ABC):
    """記事取得サービスの抽象基底クラス（Strategyパターン）"""

    @abstractmethod
    async def fetch(self, url: str) -> list[ArticleData]:
        """指定URLから記事を取得する

        Args:
            url: 取得先URL

        Returns:
            取得した記事リスト

        Raises:
            FetchError: 取得に失敗した場合
        """
        pass


class FetchError(Exception):
    """記事取得エラー"""

    def __init__(self, message: str, url: str, original_error: Optional[Exception] = None):
        self.message = message
        self.url = url
        self.original_error = original_error
        super().__init__(f"{message}: {url}")
