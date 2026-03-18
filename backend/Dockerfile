FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    requests \
    redis \
    chromadb \
    python-multipart \
    Pillow \
    pillow-heif \
    rq \
    tenacity \
    opencv-python-headless

# ── System fonts (fallback if TTF loading fails) ──────────────────────────────
# Google Fonts TTFs are bundled in frames/fonts/ and copied via COPY . /app
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-liberation \
        fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
