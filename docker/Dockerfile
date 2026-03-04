FROM python:3.11-slim

# タイムゾーン設定
ENV TZ=Asia/Tokyo

# 作業ディレクトリ設定
WORKDIR /app

# システム依存パッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Tokyo /etc/localtime \
    && echo "Asia/Tokyo" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 依存パッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# 非rootユーザーで実行
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# ポート公開
EXPOSE 8000

# アプリケーション起動
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
