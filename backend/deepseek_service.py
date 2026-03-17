import os
import json
import requests
from app.db.chroma_client import search_similar

DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# --- KLÍČOVÉ NASTAVENÍ ---
MIN_RATIO = 0.8   # 80 % délky vzoru
MAX_RATIO = 1.2   # 120 % délky vzoru

def _get_style_sample():
    """Načte Vysockého z PERSISTENTNÍ Chromy projektu vkorni."""
    results = search_similar("Владимир Высоцкий", top_k=1)
    if not results:
        return None
    return results[0]["text"]

def _call_deepseek(system_prompt: str, context: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_KEY}"
    }

    payload = {
        "model": "deepseek-chat",
        "max_tokens": 2000,
        "temperature": 0.75,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Напиши РАЗВЁРНУТНУЮ биографию в художественном стиле.\n"
                    "Опирайся ИСКЛЮЧИТЕЛЬНО на факты из контекста и перепиши их полностью:\n\n"
                    + context
                )
            }
        ]
    }

    r = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")

def generate_text(context: str) -> str:
    if not DEEPSEEK_KEY:
        raise RuntimeError("Chybí DEEPSEEK_KEY v .env")

    style_sample = _get_style_sample()
    if not style_sample:
        raise RuntimeError(
            "V Chroma NENÍ uložen stylový vzor 'Владимир Высоцкий'. "
            "Nejprve ho musíš mít v /app/chroma_data."
        )

    target_len = len(style_sample)
    min_len = int(target_len * MIN_RATIO)
    max_len = int(target_len * MAX_RATIO)

    system_prompt = (
        "НАПИШИ ПОЛНОЦЕННЫЙ ХУДОЖЕСТВЕННЫЙ БИОГРАФИЧЕСКИЙ ТЕКСТ.\n\n"
        "ПРАВИДЛА:\n"
        "- НЕ копировать Википедию\n"
        "- использовать ТОЛЬКО факты из контекста\n"
        "- писать образно, эмоционально, связно\n"
        "- структурировать как большой рассказ\n\n"
        "СТРУКТУРА:\n"
        "1) Образное вступление\n"
        "2) Детство и становление\n"
        "3) Путь к славе\n"
        "4) Влияние на культуру\n"
        "5) Характер и ценности\n"
        "6) Наследие сегодня\n\n"
        "СТИЛЕВОЙ ОРИЕНТИР (НЕ КОПИРОВАТЬ, ТОЛЬКО ТОН):\n"
        "----\n"
        + style_sample[:2000] +
        "\n----\n"
    )

    full_text = ""
    while len(full_text) < min_len:
        part = _call_deepseek(system_prompt, context)
        full_text += "\n\n" + part

    return full_text.strip()
