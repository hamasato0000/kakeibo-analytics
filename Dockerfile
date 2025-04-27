FROM python:3.12-slim

# Lambda Adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.0 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /app

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Poetryをインストール
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Poetryの設定（仮想環境を作成しない）
RUN poetry config virtualenvs.create false

# pyproject.tomlとpoetry.lockをコピー
COPY pyproject.toml poetry.lock* ./

# 依存関係をインストール
RUN poetry install --no-root --no-interaction --no-ansi

# アプリケーションファイルをコピー
COPY app/ ./app/

# ポートを公開
EXPOSE 8501

# Streamlitアプリケーションを起動
CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
