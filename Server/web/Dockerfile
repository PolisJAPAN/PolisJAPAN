FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Chromium/ChromeDriver と日本語フォント、fontconfig を導入
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-driver \
    fontconfig \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    curl unzip gnupg \
 && fc-cache -fv \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry \
 && poetry config virtualenvs.create false

# 1) まず pyproject だけをコピー（キャッシュ効率のため）
COPY pyproject.toml ./

# 2) ロックを再生成（pyproject 変更に追従）
RUN poetry lock --no-interaction --no-ansi

# 3) 生成された poetry.lock を使って install
RUN poetry install --no-root --no-interaction --no-ansi

COPY . .

ENTRYPOINT ["poetry", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--reload"]