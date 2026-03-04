"""Slack通知サービス"""

import logging

import httpx

from app.core.settings import SlackConfig
from app.services.notifier.base import (
    BaseNotifier,
    NotificationError,
    NotificationResult,
    NotificationStatus,
)
from app.services.utils.retry import with_retry

logger = logging.getLogger(__name__)


class SlackNotifier(BaseNotifier):
    """Slack Webhook を使用した通知サービス"""

    def __init__(self, config: SlackConfig):
        """
        Args:
            config: Slack設定
        """
        self.config = config

    @with_retry(max_attempts=3, delay_seconds=2, exceptions=(httpx.HTTPError,))
    async def send(self, message: str) -> NotificationResult:
        """Slackにメッセージを送信する

        Args:
            message: 送信するメッセージ

        Returns:
            送信結果
        """
        try:
            payload = {"text": message}

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.config.webhook_url,
                    json=payload,
                )

                if response.status_code == 200 and response.text == "ok":
                    logger.info("Slack通知を送信しました")
                    return NotificationResult(
                        status=NotificationStatus.SUCCESS,
                        message="送信成功",
                    )
                else:
                    error_msg = f"Slack Webhook エラー: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise NotificationError(error_msg, "Slack")

        except httpx.HTTPError as e:
            logger.error(f"Slack通知送信失敗: {e}")
            raise
        except Exception as e:
            if isinstance(e, NotificationError):
                raise
            raise NotificationError(str(e), "Slack", e)

    async def send_error(self, source_name: str, error_message: str) -> NotificationResult:
        """エラー通知を送信する"""
        message = f":x: *{source_name}*\n取得に失敗しました\n\n```{error_message}```"
        return await self.send(message)

    async def send_no_data(self, source_name: str) -> NotificationResult:
        """新着なし通知を送信する"""
        message = f":information_source: *{source_name}*\n最新の情報はありませんでした"
        return await self.send(message)

    def format_article_message(
        self,
        source_name: str,
        title: str,
        url: str,
        summary: str,
    ) -> str:
        """記事通知メッセージをフォーマットする（Slack形式）

        Args:
            source_name: ソース名
            title: 記事タイトル
            url: 記事URL
            summary: AI要約

        Returns:
            フォーマットされたメッセージ（Slack Markdown形式）
        """
        return f""":newspaper: *{source_name}* - 新着記事

*{title}*

{summary}

:link: <{url}|記事を読む>"""
