"""YAML設定ファイルの読み込みと管理"""

import os
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from app.core.config import config


class SelectorConfig(BaseModel):
    """スクレイピング用セレクタ設定"""

    article_list: str = Field(..., description="記事リストのセレクタ")
    title: str = Field(..., description="タイトルのセレクタ")
    link: str = Field(..., description="リンクのセレクタ")
    date: Optional[str] = Field(None, description="日付のセレクタ")
    content: Optional[str] = Field(None, description="本文のセレクタ")


class SourceConfig(BaseModel):
    """情報ソース設定"""

    name: str = Field(..., description="ソース名")
    url: str = Field(..., description="取得先URL")
    type: str = Field(..., description="取得タイプ: rss or scrape")
    schedule: str = Field(..., description="Cron形式のスケジュール")
    keywords: list[str] = Field(default_factory=list, description="フィルタリングキーワード")
    notify: list[str] = Field(default_factory=list, description="通知先: line, slack")
    selectors: Optional[SelectorConfig] = Field(None, description="スクレイピング用セレクタ")
    language: Optional[str] = Field(None, description="言語: en の場合日本語訳する")


class LineConfig(BaseModel):
    """LINE通知設定"""

    channel_access_token: str = Field(..., description="LINEチャネルアクセストークン")
    user_id: str = Field(..., description="通知先ユーザーID")


class SlackConfig(BaseModel):
    """Slack通知設定"""

    webhook_url: str = Field(..., description="Slack Webhook URL")


class NotificationsConfig(BaseModel):
    """通知設定"""

    line: Optional[LineConfig] = None
    slack: Optional[SlackConfig] = None


class OpenAIConfig(BaseModel):
    """OpenAI設定"""

    api_key: str = Field(..., description="OpenAI APIキー")
    model: str = Field(default="gpt-4o-mini", description="使用モデル")
    max_tokens: int = Field(default=200, description="最大トークン数")
    temperature: float = Field(default=0.3, description="温度パラメータ")


class S3Config(BaseModel):
    """​AWS S3設定"""

    enabled: bool = Field(default=False, description="S3保存を有効にする")
    bucket_name: str = Field(..., description="S3バケット名")
    aws_access_key_id: Optional[str] = Field(None, description="AWSアクセスキーID")
    aws_secret_access_key: Optional[str] = Field(None, description="AWSシークレットキー")
    aws_region: str = Field(default="ap-northeast-1", description="AWSリージョン")


class AppSettings(BaseModel):
    """アプリケーション全体の設定"""

    sources: list[SourceConfig] = Field(default_factory=list, description="情報ソース一覧")
    notifications: NotificationsConfig = Field(
        default_factory=NotificationsConfig, description="通知設定"
    )
    openai: OpenAIConfig = Field(..., description="OpenAI設定")
    s3: Optional[S3Config] = Field(None, description="S3ストレージ設定")


def expand_env_vars(value: str) -> str:
    """環境変数プレースホルダを展開する

    ${VAR_NAME} 形式の文字列を環境変数の値に置換する
    """
    pattern = r"\$\{([^}]+)\}"

    def replacer(match):
        env_var = match.group(1)
        return os.environ.get(env_var, "")

    return re.sub(pattern, replacer, value)


def process_config_value(value):
    """設定値を再帰的に処理し、環境変数を展開する"""
    if isinstance(value, str):
        return expand_env_vars(value)
    elif isinstance(value, dict):
        return {k: process_config_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [process_config_value(item) for item in value]
    return value


def load_settings(config_path: Optional[str] = None) -> AppSettings:
    """YAML設定ファイルを読み込む

    Args:
        config_path: 設定ファイルのパス（省略時は環境変数から取得）

    Returns:
        AppSettings: アプリケーション設定

    Raises:
        FileNotFoundError: 設定ファイルが見つからない場合
        ValueError: 設定ファイルの形式が不正な場合
    """
    if config_path is None:
        config_path = config.sources_config_path

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    if raw_config is None:
        raise ValueError(f"設定ファイルが空です: {config_path}")

    # 環境変数を展開
    processed_config = process_config_value(raw_config)

    # Pydanticモデルにパース
    return AppSettings(**processed_config)


# 設定のキャッシュ（起動時に1回だけ読み込む）
_settings_cache: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """キャッシュされた設定を取得する"""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = load_settings()
    return _settings_cache


def reload_settings() -> AppSettings:
    """設定を再読み込みする"""
    global _settings_cache
    _settings_cache = load_settings()
    return _settings_cache
