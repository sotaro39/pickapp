"""AI要約サービス（OpenAI）"""

import logging
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI

from app.core.settings import OpenAIConfig
from app.services.utils.retry import with_retry

logger = logging.getLogger(__name__)


@dataclass
class ArticleSummary:
    """記事要約結果"""
    summary: str  # 3行要約
    recommendation: int  # 初心者おすすめ度 (1-5)
    recommendation_reason: str  # おすすめ理由
    title_ja: Optional[str] = None  # タイトルの日本語訳（英語サイトの場合）


class SummarizerService:
    """OpenAI APIを使用した記事要約サービス

    記事の内容を3行程度に要約する
    """

    def __init__(self, config: OpenAIConfig):
        """
        Args:
            config: OpenAI設定
        """
        self.config = config
        self.client = AsyncOpenAI(api_key=config.api_key)

    @with_retry(max_attempts=3, delay_seconds=2, exceptions=(Exception,))
    async def summarize(self, title: str, content: Optional[str]) -> str:
        """記事を3行で要約する（後方互換性のため維持）

        Args:
            title: 記事タイトル
            content: 記事本文（なければタイトルのみで要約）

        Returns:
            3行の要約テキスト
        """
        result = await self.summarize_with_recommendation(title, content)
        return result.summary

    @with_retry(max_attempts=3, delay_seconds=2, exceptions=(Exception,))
    async def summarize_with_recommendation(self, title: str, content: Optional[str], is_english: bool = False) -> ArticleSummary:
        """記事を3行で要約し、初心者おすすめ度も評価する

        Args:
            title: 記事タイトル
            content: 記事本文（なければタイトルのみで要約）
            is_english: 英語記事の場合True（日本語訳も生成）

        Returns:
            ArticleSummary: 要約とおすすめ度
        """
        if not content:
            prompt_content = f"タイトル: {title}\n\n（本文なし - タイトルから内容を推測してください）"
        else:
            truncated_content = content[:3000] if len(content) > 3000 else content
            prompt_content = f"タイトル: {title}\n\n本文:\n{truncated_content}"

        # 英語記事用のプロンプト
        if is_english:
            system_prompt = (
                "あなたは技術記事を簡潔に要約するアシスタントです。\n"
                "この記事は英語で書かれています。日本語で以下の形式で回答してください：\n\n"
                "【タイトル日本語訳】\n"
                "（タイトルの日本語訳を1行で）\n\n"
                "【要約】\n"
                "・ポイント1\n"
                "・ポイント2\n"
                "・ポイント3\n\n"
                "【初心者おすすめ度】\n"
                "スコア: X（1-5の数字のみ）\n"
                "理由: 一行で簡潔に\n\n"
                "ルール：\n"
                "- タイトルは自然な日本語に訳す\n"
                "- 要約は必ず3行（3つのポイント）、日本語で\n"
                "- 各行は「・」で始める\n"
                "- 技術的なキーワードを含める\n"
                "- おすすめ度は1=難しい、5=初心者にぴったり"
            )
        else:
            system_prompt = (
                "あなたは技術記事を簡潔に要約するアシスタントです。\n"
                "以下の形式で回答してください：\n\n"
                "【要約】\n"
                "・ポイント1\n"
                "・ポイント2\n"
                "・ポイント3\n\n"
                "【初心者おすすめ度】\n"
                "スコア: X（1-5の数字のみ）\n"
                "理由: 一行で簡潔に\n\n"
                "ルール：\n"
                "- 要約は必ず3行（3つのポイント）\n"
                "- 各行は「・」で始める\n"
                "- 技術的なキーワードを含める\n"
                "- おすすめ度は1=難しい、5=初心者にぴったり\n"
                "- 日本語で回答する"
            )

        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_content},
                ],
                max_tokens=400 if is_english else 350,
                temperature=self.config.temperature,
            )

            response_text = response.choices[0].message.content.strip()
            logger.debug(f"要約生成完了: {title[:30]}...")
            
            # レスポンスをパース
            return self._parse_response(response_text, is_english)

        except Exception as e:
            logger.error(f"要約生成に失敗: {e}")
            raise

    def _parse_response(self, response_text: str, is_english: bool = False) -> ArticleSummary:
        """AIのレスポンスをパースする"""
        lines = response_text.split("\n")
        
        summary_lines = []
        recommendation = 3  # デフォルト
        recommendation_reason = ""
        title_ja = None
        
        in_title_ja = False
        in_summary = False
        in_recommendation = False
        
        for line in lines:
            line = line.strip()
            if "【タイトル日本語訳】" in line:
                in_title_ja = True
                in_summary = False
                in_recommendation = False
                continue
            elif "【要約】" in line:
                in_title_ja = False
                in_summary = True
                in_recommendation = False
                continue
            elif "【初心者おすすめ度】" in line:
                in_title_ja = False
                in_summary = False
                in_recommendation = True
                continue
            
            if in_title_ja and line:
                title_ja = line
                in_title_ja = False
            elif in_summary and line.startswith("・"):
                summary_lines.append(line)
            elif in_recommendation:
                if line.startswith("スコア:") or line.startswith("スコア："):
                    try:
                        score_str = line.replace("スコア:", "").replace("スコア：", "").strip()
                        recommendation = int(score_str[0])
                        recommendation = max(1, min(5, recommendation))
                    except:
                        recommendation = 3
                elif line.startswith("理由:") or line.startswith("理由："):
                    recommendation_reason = line.replace("理由:", "").replace("理由：", "").strip()
        
        summary = "\n".join(summary_lines) if summary_lines else response_text
        
        return ArticleSummary(
            summary=summary,
            recommendation=recommendation,
            recommendation_reason=recommendation_reason or "技術記事です",
            title_ja=title_ja
        )


# サービスインスタンスのキャッシュ
_summarizer_instance: Optional[SummarizerService] = None


def get_summarizer(config: OpenAIConfig) -> SummarizerService:
    """要約サービスのインスタンスを取得"""
    global _summarizer_instance
    if _summarizer_instance is None:
        _summarizer_instance = SummarizerService(config)
    return _summarizer_instance
