"""APSchedulerによるスケジュール管理"""

import logging
from typing import Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.settings import AppSettings

# 日本時間タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

logger = logging.getLogger(__name__)


class SchedulerService:
    """スケジュール管理サービス

    APSchedulerを使用して、設定ファイルに定義されたスケジュールに従って
    記事取得ジョブを実行する
    """

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._settings: Optional[AppSettings] = None

    def start(self, settings: AppSettings) -> None:
        """スケジューラを起動する

        Args:
            settings: アプリケーション設定
        """
        self._settings = settings

        # スケジューラ作成
        self.scheduler = AsyncIOScheduler(
            timezone="Asia/Tokyo",
            job_defaults={
                "coalesce": True,  # ミスしたジョブをまとめる
                "max_instances": 1,
                "misfire_grace_time": 300,  # 5分以内なら実行
            },
        )

        # ソースごとにジョブを登録
        for source in settings.sources:
            self._add_source_job(source)

        # 再送キュー処理ジョブを登録（1分間隔）
        self.scheduler.add_job(
            self._process_retry_queue,
            trigger="interval",
            minutes=1,
            id="retry_queue_processor",
            name="再送キュー処理",
        )

        self.scheduler.start()
        logger.info(f"スケジューラ起動: {len(settings.sources)}個のジョブを登録")

    def shutdown(self) -> None:
        """スケジューラを停止する"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("スケジューラ停止")

    def _add_source_job(self, source) -> None:
        """ソースの取得ジョブを追加する"""
        from app.jobs.fetch_job import execute_fetch_job

        try:
            # Cron式をパース（日本時間）
            trigger = CronTrigger.from_crontab(source.schedule, timezone=JST)

            self.scheduler.add_job(
                execute_fetch_job,
                trigger=trigger,
                id=f"fetch_{source.name}",
                name=f"記事取得: {source.name}",
                kwargs={"source_name": source.name},
            )

            logger.info(f"ジョブ登録: {source.name} ({source.schedule})")

        except Exception as e:
            logger.error(f"ジョブ登録失敗: {source.name} - {e}")

    async def _process_retry_queue(self) -> None:
        """再送キューを処理する"""
        from app.core.database import AsyncSessionLocal
        from app.core.settings import get_settings
        from app.services.retry_queue import RetryQueueService

        try:
            settings = get_settings()
            retry_service = RetryQueueService(settings)

            async with AsyncSessionLocal() as db:
                processed = await retry_service.process_pending(db)
                if processed > 0:
                    logger.info(f"再送キュー処理: {processed}件")

        except Exception as e:
            logger.error(f"再送キュー処理エラー: {e}")

    def get_jobs(self) -> list[dict]:
        """登録されているジョブ一覧を取得する"""
        if not self.scheduler:
            return []

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
            })
        return jobs


# シングルトンインスタンス
scheduler_service = SchedulerService()
