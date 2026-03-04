"""リトライ処理用ユーティリティ"""

import asyncio
import logging
from functools import wraps
from typing import Tuple, Type

logger = logging.getLogger(__name__)


def with_retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_delay_seconds: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """指数バックオフでリトライするデコレータ

    Args:
        max_attempts: 最大試行回数
        delay_seconds: 初回リトライまでの待機時間
        backoff_multiplier: リトライごとの待機時間の倍率
        max_delay_seconds: 最大待機時間
        exceptions: リトライ対象の例外
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            delay = delay_seconds

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )

                    await asyncio.sleep(delay)
                    delay = min(delay * backoff_multiplier, max_delay_seconds)

            raise last_exception

        return wrapper

    return decorator
