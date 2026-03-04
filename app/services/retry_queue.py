"""通知再送キューサービス"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import AppSettings
from app.models.retry_queue import NotificationRetryQueue, RetryStatus
from app.services.notifier.base import NotificationResult, NotificationStatus
from app.services.notifier.line import LineNotifier
from app.services.notifier.slack import SlackNotifier

logger = logging.getLogger(__name__)


class RetryQueueService:
    """通知再送キューサービス

    通知送信に失敗した場合、このサービスを使って再送キューに追加し、
    後で自動的に再送する
    """

    MAX_ATTEMPTS = 5

    def __init__(self, settings: AppSettings):
        """
        Args:
            settings: アプリケーション設定
        """
        self.settings = settings

    async def enqueue(
        self,
        db: AsyncSession,
        notification_type: str,
        message: str,
        source_name: str,
        error: Optional[str] = None,
    ) -> NotificationRetryQueue:
        """再送キューに追加する

        Args:
            db: データベースセッション
            notification_type: 通知タイプ（line, slack）
            message: 送信メッセージ
            source_name: ソース名
            error: エラーメッセージ

        Returns:
            作成されたキューアイテム
        """
        retry_item = NotificationRetryQueue(
            notification_type=notification_type,
            message=message,
            source_name=source_name,
            attempt_count=0,
            next_retry_at=datetime.utcnow() + timedelta(seconds=60),  # 1分後
            status=RetryStatus.PENDING.value,
            last_error=error,
        )

        db.add(retry_item)
        await db.commit()
        await db.refresh(retry_item)

        logger.info(f"再送キューに追加: {notification_type} - {source_name}")
        return retry_item

    async def process_pending(self, db: AsyncSession) -> int:
        """保留中の再送キューを処理する

        Args:
            db: データベースセッション

        Returns:
            処理したアイテム数
        """
        # 再送対象を取得
        stmt = select(NotificationRetryQueue).where(
            and_(
                NotificationRetryQueue.status == RetryStatus.PENDING.value,
                NotificationRetryQueue.next_retry_at <= datetime.utcnow(),
            )
        ).limit(100)

        result = await db.execute(stmt)
        pending_items = result.scalars().all()

        if not pending_items:
            return 0

        processed_count = 0
        for item in pending_items:
            await self._process_item(db, item)
            processed_count += 1

        await db.commit()
        logger.info(f"再送キュー処理完了: {processed_count}件")
        return processed_count

    async def _process_item(
        self,
        db: AsyncSession,
        item: NotificationRetryQueue,
    ) -> None:
        """個別のキューアイテムを処理する"""
        try:
            # 通知サービスを取得
            notifier = self._get_notifier(item.notification_type)
            if not notifier:
                item.status = RetryStatus.FAILED.value
                item.last_error = f"Unknown notification type: {item.notification_type}"
                return

            # 送信を試行
            result = await notifier.send(item.message)

            if result.status == NotificationStatus.SUCCESS:
                item.status = RetryStatus.COMPLETED.value
                logger.info(f"再送成功: {item.id}")
            else:
                await self._handle_failure(item, result.error or "Unknown error")

        except Exception as e:
            await self._handle_failure(item, str(e))

    async def _handle_failure(
        self,
        item: NotificationRetryQueue,
        error: str,
    ) -> None:
        """送信失敗時の処理"""
        item.attempt_count += 1
        item.last_error = error

        if item.attempt_count >= self.MAX_ATTEMPTS:
            item.status = RetryStatus.FAILED.value
            logger.error(f"再送失敗（最大試行回数超過）: {item.id} - {error}")
        else:
            # 次のリトライ時刻を設定
            interval = item.get_next_retry_interval()
            item.next_retry_at = datetime.utcnow() + timedelta(seconds=interval)
            logger.warning(
                f"再送失敗（{item.attempt_count}/{self.MAX_ATTEMPTS}）: {item.id} - "
                f"次回: {interval}秒後"
            )

    def _get_notifier(self, notification_type: str) -> Optional[LineNotifier | SlackNotifier]:
        """通知タイプに応じたNotifierを取得"""
        if notification_type == "line" and self.settings.notifications.line:
            return LineNotifier(self.settings.notifications.line)
        elif notification_type == "slack" and self.settings.notifications.slack:
            return SlackNotifier(self.settings.notifications.slack)
        return None
