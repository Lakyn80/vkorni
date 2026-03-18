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

# ── System fonts + wget ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget \
        fonts-liberation \
        fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

# ── Download Google Fonts for memorial frames ─────────────────────────────────
RUN mkdir -p /app/frames/fonts && \
    wget -q -O /app/frames/fonts/Cinzel-Regular.ttf \
        "https://github.com/google/fonts/raw/main/ofl/cinzel/static/Cinzel-Regular.ttf" || true && \
    wget -q -O /app/frames/fonts/PlayfairDisplay-Regular.ttf \
        "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/static/PlayfairDisplay-Regular.ttf" || true && \
    wget -q -O /app/frames/fonts/EBGaramond-Regular.ttf \
        "https://github.com/google/fonts/raw/main/ofl/ebgaramond/static/EBGaramond-Regular.ttf" || true && \
    wget -q -O /app/frames/fonts/LibreBaskerville-Regular.ttf \
        "https://github.com/google/fonts/raw/main/ofl/librebaskerville/LibreBaskerville-Regular.ttf" || true && \
    wget -q -O /app/frames/fonts/Cormorant-Regular.ttf \
        "https://github.com/google/fonts/raw/main/ofl/cormorant/static/Cormorant-Regular.ttf" || true && \
    wget -q -O /app/frames/fonts/CrimsonText-Regular.ttf \
        "https://github.com/google/fonts/raw/main/ofl/crimsontext/CrimsonText-Regular.ttf" || true && \
    wget -q -O /app/frames/fonts/JosefinSlab-Regular.ttf \
        "https://github.com/google/fonts/raw/main/ofl/josefinslab/static/JosefinSlab-Regular.ttf" || true && \
    wget -q -O /app/frames/fonts/Spectral-Regular.ttf \
        "https://github.com/google/fonts/raw/main/ofl/spectral/Spectral-Regular.ttf" || true && \
    wget -q -O /app/frames/fonts/Cardo-Regular.ttf \
        "https://github.com/google/fonts/raw/main/ofl/cardo/Cardo-Regular.ttf" || true && \
    wget -q -O /app/frames/fonts/IMFellEnglish-Regular.ttf \
        "https://github.com/google/fonts/raw/main/ofl/imfellenglish/IMFellEnglish-Regular.ttf" || true

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
