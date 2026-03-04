"""データベース接続とセッション管理"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import config

# 非同期エンジンの作成
engine = create_async_engine(
    config.database_url,
    echo=config.is_development,
    future=True,
)

# 非同期セッションファクトリ
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """SQLAlchemyベースクラス"""

    pass


async def get_db() -> AsyncSession:
    """データベースセッションを取得する依存性"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """データベースを初期化する（テーブル作成）"""
    async with engine.begin() as conn:
        # 全てのモデルをインポートしてテーブルを作成
        from app.models import article, retry_queue  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """データベース接続を閉じる"""
    await engine.dispose()
