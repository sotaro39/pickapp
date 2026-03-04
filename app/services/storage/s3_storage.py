"""AWS S3に記事をテキストファイルとして保存するサービス"""

import logging
from datetime import datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Storage:
    """S3ストレージサービス"""

    def __init__(
        self,
        bucket_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region: str = "ap-northeast-1",
    ):
        """
        Args:
            bucket_name: S3バケット名
            aws_access_key_id: AWSアクセスキーID (省略時は環境変数/IAMロール)
            aws_secret_access_key: AWSシークレットキー (省略時は環境変数/IAMロール)
            aws_region: AWSリージョン
        """
        self.bucket_name = bucket_name
        self.region = aws_region

        # 認証情報が明示的に指定されている場合のみ使用
        if aws_access_key_id and aws_secret_access_key:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_region,
            )
        else:
            # 環境変数やIAMロールから認証
            self.s3_client = boto3.client("s3", region_name=aws_region)

    def _generate_file_path(
        self, source_name: str, article_number: int, timestamp: Optional[datetime] = None
    ) -> str:
        """ファイルパスを生成

        Format: YYYYMMDD/YYYYMMDDHHmm_NNN_ソース名.txt

        Args:
            source_name: ソース名（例: Zenn, Qiita）
            article_number: 記事番号（001, 002...）
            timestamp: タイムスタンプ（省略時は現在時刻）

        Returns:
            S3オブジェクトキー
        """
        if timestamp is None:
            timestamp = datetime.now()

        date_folder = timestamp.strftime("%Y%m%d")
        datetime_str = timestamp.strftime("%Y%m%d%H%M%S")
        # サニタイズ：ファイル名に使えない文字を置換
        safe_source_name = source_name.replace("/", "_").replace("\\", "_").replace(" ", "_")

        filename = f"{datetime_str}_{article_number:03d}_{safe_source_name}.txt"

        return f"{date_folder}/{filename}"

    def _format_article_content(
        self,
        title: str,
        url: str,
        source_name: str,
        summary: str,
        recommendation: int,
        recommendation_reason: str,
        published_at: Optional[str] = None,
    ) -> str:
        """記事内容をテキスト形式にフォーマット

        Args:
            title: 記事タイトル
            url: 記事URL
            source_name: ソース名
            summary: AI要約
            recommendation: おすすめ度（1-5）
            recommendation_reason: おすすめ理由
            published_at: 公開日時

        Returns:
            フォーマット済みテキスト
        """
        stars = "★" * recommendation + "☆" * (5 - recommendation)
        
        lines = [
            "=" * 60,
            f"📡 ソース: {source_name}",
            "=" * 60,
            "",
            f"📝 タイトル: {title}",
            "",
            f"🔗 URL: {url}",
            "",
        ]
        
        if published_at:
            lines.append(f"📅 公開日: {published_at}")
            lines.append("")

        lines.extend([
            "-" * 60,
            "【AI要約】",
            summary,
            "-" * 60,
            "",
            f"⭐ 初心者おすすめ度: {stars} ({recommendation}/5)",
            f"   理由: {recommendation_reason}",
            "",
            "=" * 60,
            f"保存日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
        ])

        return "\n".join(lines)

    async def save_article(
        self,
        title: str,
        url: str,
        source_name: str,
        summary: str,
        recommendation: int,
        recommendation_reason: str,
        article_number: int,
        published_at: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """記事をS3に保存

        Args:
            title: 記事タイトル
            url: 記事URL
            source_name: ソース名
            summary: AI要約
            recommendation: おすすめ度
            recommendation_reason: おすすめ理由
            article_number: 記事番号
            published_at: 公開日時
            timestamp: 保存時のタイムスタンプ

        Returns:
            保存先のS3パス

        Raises:
            ClientError: S3操作エラー
        """
        # ファイルパス生成
        s3_key = self._generate_file_path(source_name, article_number, timestamp)

        # コンテンツ生成
        content = self._format_article_content(
            title=title,
            url=url,
            source_name=source_name,
            summary=summary,
            recommendation=recommendation,
            recommendation_reason=recommendation_reason,
            published_at=published_at,
        )

        try:
            # S3にアップロード
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=content.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )
            logger.info(f"S3に記事を保存しました: s3://{self.bucket_name}/{s3_key}")
            return f"s3://{self.bucket_name}/{s3_key}"

        except ClientError as e:
            logger.error(f"S3保存エラー: {e}")
            raise

    async def save_articles_batch(
        self,
        articles: list[dict],
        source_name: str,
        timestamp: Optional[datetime] = None,
    ) -> list[str]:
        """複数の記事をバッチでS3に保存

        Args:
            articles: 記事情報のリスト
                [{"title": str, "url": str, "summary": str, 
                  "recommendation": int, "recommendation_reason": str, 
                  "published_at": str (optional)}]
            source_name: ソース名
            timestamp: 保存時のタイムスタンプ

        Returns:
            保存先S3パスのリスト
        """
        if timestamp is None:
            timestamp = datetime.now()

        saved_paths = []
        for i, article in enumerate(articles, start=1):
            try:
                path = await self.save_article(
                    title=article["title"],
                    url=article["url"],
                    source_name=source_name,
                    summary=article["summary"],
                    recommendation=article["recommendation"],
                    recommendation_reason=article["recommendation_reason"],
                    article_number=i,
                    published_at=article.get("published_at"),
                    timestamp=timestamp,
                )
                saved_paths.append(path)
            except ClientError as e:
                logger.error(f"記事保存失敗 ({article.get('title', 'unknown')}): {e}")
                saved_paths.append(f"ERROR: {str(e)}")

        return saved_paths

    def check_connection(self) -> bool:
        """S3接続確認

        Returns:
            接続成功時True
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3バケット接続確認OK: {self.bucket_name}")
            return True
        except ClientError as e:
            logger.error(f"S3バケット接続エラー: {e}")
            return False
