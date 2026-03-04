"""LINE通知サービス"""

import logging

import httpx

from app.core.settings import LineConfig
from app.services.notifier.base import (
    BaseNotifier,
    NotificationError,
    NotificationResult,
    NotificationStatus,
)
from app.services.utils.retry import with_retry

logger = logging.getLogger(__name__)


class LineNotifier(BaseNotifier):
    """LINE Messaging API を使用した通知サービス"""

    API_URL = "https://api.line.me/v2/bot/message/push"

    def __init__(self, config: LineConfig):
        """
        Args:
            config: LINE設定
        """
        self.config = config
        self.headers = {
            "Authorization": f"Bearer {config.channel_access_token}",
            "Content-Type": "application/json",
        }

    @with_retry(max_attempts=3, delay_seconds=2, exceptions=(httpx.HTTPError,))
    async def send(self, message: str) -> NotificationResult:
        """LINEにメッセージを送信する

        Args:
            message: 送信するメッセージ

        Returns:
            送信結果
        """
        try:
            payload = {
                "to": self.config.user_id,
                "messages": [{"type": "text", "text": message}],
            }

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.API_URL,
                    json=payload,
                    headers=self.headers,
                )

                if response.status_code == 200:
                    logger.info("LINE通知を送信しました")
                    return NotificationResult(
                        status=NotificationStatus.SUCCESS,
                        message="送信成功",
                    )
                else:
                    error_msg = f"LINE API エラー: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise NotificationError(error_msg, "LINE")

        except httpx.HTTPError as e:
            logger.error(f"LINE通知送信失敗: {e}")
            raise
        except Exception as e:
            if isinstance(e, NotificationError):
                raise
            raise NotificationError(str(e), "LINE", e)

    async def send_error(self, source_name: str, error_message: str) -> NotificationResult:
        """エラー通知を送信する"""
        message = f"❌ {source_name}\n取得に失敗しました\n\nエラー: {error_message}"
        return await self.send(message)

    async def send_no_data(self, source_name: str) -> NotificationResult:
        """新着なし通知を送信する"""
        message = f"ℹ️ {source_name}\n最新の情報はありませんでした"
        return await self.send(message)

    def format_article_message(
        self,
        source_name: str,
        title: str,
        url: str,
        summary: str,
    ) -> str:
        """記事通知メッセージをフォーマットする

        Args:
            source_name: ソース名
            title: 記事タイトル
            url: 記事URL
            summary: AI要約

        Returns:
            フォーマットされたメッセージ
        """
        return f"""📰 {source_name} - 新着記事

【{title}】

{summary}

🔗 {url}"""
