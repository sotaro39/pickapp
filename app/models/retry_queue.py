"""通知再送キューモデル"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RetryStatus(str, Enum):
    """再送ステータス"""

    PENDING = "pending"  # 再送待ち
    COMPLETED = "completed"  # 送信成功
    FAILED = "failed"  # 最終的に失敗


class NotificationRetryQueue(Base):
    """通知再送キューテーブル

    通知送信に失敗した場合、このキューに追加して後で再送する
    """

    __tablename__ = "notification_retry_queue"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 通知情報
    notification_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="通知タイプ: line, slack"
    )
    message: Mapped[str] = mapped_column(Text, nullable=False, comment="通知メッセージ")
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="ソース名")

    # リトライ状態
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="試行回数"
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, default=5, nullable=False, comment="最大試行回数"
    )
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="次回リトライ日時"
    )
    status: Mapped[str] = mapped_column(
        String(20), default=RetryStatus.PENDING.value, nullable=False, comment="ステータス"
    )

    # エラー情報
    last_error: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="最後のエラーメッセージ"
    )

    # タイムスタンプ
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, comment="作成日時"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="更新日時"
    )

    # インデックス
    __table_args__ = (
        Index("idx_retry_queue_status_next", "status", "next_retry_at"),
        Index("idx_retry_queue_notification_type", "notification_type"),
    )

    # リトライ間隔（秒）: 1分, 5分, 15分, 1時間, 2時間
    RETRY_INTERVALS = [60, 300, 900, 3600, 7200]

    def get_next_retry_interval(self) -> int:
        """次のリトライ間隔を取得（秒）"""
        index = min(self.attempt_count, len(self.RETRY_INTERVALS) - 1)
        return self.RETRY_INTERVALS[index]

    def __repr__(self) -> str:
        return f"<NotificationRetryQueue(id={self.id}, type='{self.notification_type}', status='{self.status}')>"
