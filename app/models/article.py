"""取得済み記事モデル（重複通知防止用）"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Article(Base):
    """取得済み記事テーブル

    同じ記事を重複して通知しないために、取得済みのURLを記録する
    """

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 記事情報
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="ソース名")
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True, comment="記事URL")
    title: Mapped[str] = mapped_column(String(512), nullable=False, comment="記事タイトル")
    content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="記事本文（抜粋）")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="AI要約")

    # 通知状態
    is_notified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="通知済みフラグ"
    )
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="通知日時"
    )

    # タイムスタンプ
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="記事公開日時"
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, comment="取得日時"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, comment="作成日時"
    )

    # インデックス
    __table_args__ = (
        Index("idx_articles_source_name", "source_name"),
        Index("idx_articles_fetched_at", "fetched_at"),
        Index("idx_articles_is_notified", "is_notified"),
    )

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title='{self.title[:30]}...', source='{self.source_name}')>"
