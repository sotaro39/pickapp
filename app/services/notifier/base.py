"""通知サービスの抽象基底クラス"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class NotificationStatus(str, Enum):
    """通知ステータス"""

    SUCCESS = "success"  # 送信成功
    FAILED = "failed"  # 送信失敗
    NO_DATA = "no_data"  # 新着データなし


@dataclass
class NotificationResult:
    """通知結果"""

    status: NotificationStatus
    message: Optional[str] = None
    error: Optional[str] = None


class BaseNotifier(ABC):
    """通知サービスの抽象基底クラス"""

    @abstractmethod
    async def send(self, message: str) -> NotificationResult:
        """通知を送信する

        Args:
            message: 送信するメッセージ

        Returns:
            送信結果
        """
        pass

    @abstractmethod
    async def send_error(self, source_name: str, error_message: str) -> NotificationResult:
        """エラー通知を送信する

        Args:
            source_name: ソース名
            error_message: エラーメッセージ

        Returns:
            送信結果
        """
        pass

    @abstractmethod
    async def send_no_data(self, source_name: str) -> NotificationResult:
        """新着なし通知を送信する

        Args:
            source_name: ソース名

        Returns:
            送信結果
        """
        pass


class NotificationError(Exception):
    """通知エラー"""

    def __init__(self, message: str, platform: str, original_error: Optional[Exception] = None):
        self.message = message
        self.platform = platform
        self.original_error = original_error
        super().__init__(f"[{platform}] {message}")
