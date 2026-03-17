import os
import json
import redis
import requests

DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY")
REDIS_HOST = os.getenv("REDIS_HOST", "vkorni-redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# >>>>>> ZMĚNA: BEREME STYL Z CHROMY, NE Z REDIS <<<<<<
def _load_style_from_chroma():
    from app.db.chroma_client import search_similar

    results = search_similar("Владимир Высоцкий", top_k=1)
    if not results:
        return None

    return results[0]["text"]
# >>>>>> KONEC ZMĚNY <<<<<<


def generate_text(context: str) -> str:
    if not DEEPSEEK_KEY:
        raise RuntimeError("Chybí DEEPSEEK_KEY v .env")

    # >>>>>> ZMĚNA: voláme chromu místo redis <<<<<<
    style_sample = _load_style_from_chroma()
    # >>>>>> KONEC ZMĚNY <<<<<<

    system_prompt = (
        "НАПИШИ НОВЫЙ, БОЛЬШОЙ И ПОЛНОЦЕННЫЙ БИОГРАФИЧЕСКИЙ ТЕКСТ НА РУССКОМ.\n\n"
        "ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:\n"
        "1) НИКОГДА НЕ КОПИРОВАТЬ ТЕКСТ ИЗ ВИКИПЕДИИ.\n"
        "2) НЕ ДЕЛАТЬ КОРОТКОЕ РЕЗЮМЕ — ПИСАТЬ РАЗВЕРНУТЫЙ НАРРАТИВ (300–600 слов).\n"
        "3) ПИСАТЬ ХУДОЖЕСТВЕННЫМ, ЭМОЦИОНАЛЬНЫМ СТИЛЕМ.\n"
        "4) ИСПОЛЬЗОВАТЬ ФАКТЫ ИЗ КОНТЕКСТА, НО ПЕРЕФОРМУЛИРОВАТЬ ИХ ПОЛНОСТЬЮ.\n\n"
        "СТРУКТУРА ТЕКСТА:\n"
        "- Сильное вступление (образное, метафоричное)\n"
        "- Детство и становление\n"
        "- Главные достижения и влияние на культуру\n"
        "- Личность, характер, ценности\n"
        "- Наследие и память сегодня\n\n"
    )

    if style_sample:
        system_prompt += (
            "СТИЛЕВОЙ ОРИЕНТИР (НЕ КОПИРОВАТЬ, ТОЛЬКО ТОН И ПОЭТИКУ):\n"
            "----\n"
            + style_sample[:2500] +
            "\n----\n"
        )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_KEY}"
    }

    payload = {
        "model": "deepseek-chat",
        "max_tokens": 1500,
        "temperature": 0.75,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Напиши развернутную биографию в художественном стиле.\n"
                    "Опирайся на эти факты, но перепиши их полностью своими словами:\n\n"
                    + context
                )
            }
        ]
    }

    r = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=90)
    r.raise_for_status()

    data = r.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")
