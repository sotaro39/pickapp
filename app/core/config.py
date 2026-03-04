"""環境変数の設定管理"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """アプリケーション設定（環境変数から読み込み）"""

    # 環境設定
    environment: str = "development"

    # データベース
    database_url: str = "sqlite+aiosqlite:///./pickapp.db"

    # OpenAI
    openai_api_key: str = ""

    # LINE
    line_channel_access_token: str = ""
    line_user_id: str = ""

    # Slack
    slack_webhook_url: str = ""

    # タイムゾーン
    tz: str = "Asia/Tokyo"

    # 設定ファイルパス
    sources_config_path: str = "config/sources.yaml"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_development(self) -> bool:
        """開発環境かどうか"""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """本番環境かどうか"""
        return self.environment == "production"


@lru_cache
def get_config() -> Config:
    """設定のシングルトンインスタンスを取得"""
    return Config()


config = get_config()
