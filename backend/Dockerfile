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
    opencv-python-headless \
    sqlalchemy \
    "python-jose[cryptography]" \
    "passlib[bcrypt]"

# ── System fallback fonts ─────────────────────────────────────────────────────
# Google Fonts TTFs are in ./backend/frames/fonts/ (mounted as volume at runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-liberation fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
