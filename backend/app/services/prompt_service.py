"""
prompt_service.py
-----------------
Modular prompt building for source-bound biography generation.
"""

from __future__ import annotations

import random
import re
from typing import Any

ANGLES: list[dict] = [
    {"id": "source_bound_profile", "directive": "Drž se výhradně zdroje.", "tone": "důstojný, čtivý"},
    {"id": "source_bound_chronology", "directive": "Zachovej chronologii a význam faktů.", "tone": "klidný, přesný"},
    {"id": "source_bound_memorial", "directive": "Přepiš suchá fakta do čitelného pamětního vyprávění bez halucinací.", "tone": "živý, klidný, lehce literární"},
]

SECTION_TEMPLATES: dict[str, list[str]] = {
    "military_memorial": [
        "Nadpis: celé jméno a krátce kdo byl.",
        "Krátký úvod o člověku a době, kterou prošel.",
        "Raná léta",
        "Začátek služby",
        "Velká vlastenecká válka",
        "Poválečná cesta",
        "Vyznamenání",
        "Památka",
    ],
    "general_memorial": [
        "Nadpis: celé jméno a krátce kdo byl.",
        "Krátký úvod o člověku a době, kterou prošel.",
        "Raná léta",
        "Hlavní životní cesta",
        "Práce a služba",
        "Pozdější období",
        "Ocenění nebo doložené výsledky",
        "Památka",
    ],
}

PROMPT_PROFILES: dict[str, dict[str, Any]] = {
    "vkorni_memorial": {
        "name": "Vkorni memorial narrative",
        "length": "300–700 slov",
        "section_template": "military_memorial",
        "intro": (
            "Napiš biografii pro pamětní projekt „Korни“ — Vkorni.com.\n\n"
            "Úkolem je převést suchý encyklopedický text do živého, čitelného a důstojného pamětního životopisu."
        ),
        "style_rules": [
            "Nepiš jako Wikipedie.",
            "Nepiš jako vojenská karta ani slepený seznam funkcí a dat.",
            "Piš jako čitelný pamětní příběh.",
            "Text má být živý, důstojný, klidný a trochu literární.",
            "Čitelnost zlepšuj strukturou, rytmem a přechody, ne fantazií.",
            "Nepřeháněj poetiku ani heroismus.",
        ],
        "ordering_rules": [
            "Nezačínej text náhodným detailem z konce článku.",
            "Pozdní paměťové informace, přejmenování ulic, pomníky, názvy škol, muzeí a podobné odkazy patří až do části „Památka“ na konci.",
            "Nemíchej dohromady bojovou biografii, poválečný život a pozdější připomínky.",
        ],
    }
}


def pick_angle(exclude_ids: list[str] | None = None) -> dict:
    pool = [a for a in ANGLES if not exclude_ids or a["id"] not in exclude_ids]
    if not pool:
        pool = ANGLES
    return random.choice(pool)


def _extract_person_name(context: str) -> str:
    if not isinstance(context, str):
        return ""

    match = re.search(r"^Полное имя:\s*(.+)$", context, flags=re.MULTILINE)
    if match:
        return match.group(1).strip()

    match = re.search(r"^Name:\s*(.+)$", context, flags=re.MULTILINE)
    if match:
        return match.group(1).strip()

    return ""


def _format_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _build_structure_block(section_template: str) -> str:
    sections = SECTION_TEMPLATES.get(section_template, SECTION_TEMPLATES["general_memorial"])
    return "Struktura:\n" + "\n".join(f"{index}. {item}" for index, item in enumerate(sections, start=1))


def _build_base_rules_block() -> str:
    return (
        "NEJDŮLEŽITĚJŠÍ PRAVIDLO:\n"
        "Smíš použít POUZE informace, které jsou výslovně obsažené ve zdrojovém textu.\n"
        "Nesmíš použít žádné vlastní znalosti, domněnky, odhady, doplnění ani informace z paměti modelu.\n\n"
        "Zachovej přesně:\n"
        "- jméno,\n"
        "- data narození a úmrtí,\n"
        "- hodnosti,\n"
        "- místa služby,\n"
        "- války,\n"
        "- vyznamenání,\n"
        "- historické události,\n"
        "- časové pořadí hlavních životních etap.\n\n"
        "Nevymýšlej:\n"
        "- osobní vlastnosti,\n"
        "- vzpomínky,\n"
        "- rodinné detaily,\n"
        "- hrdinské scény,\n"
        "- emoce,\n"
        "- události, které nejsou ve zdroji.\n\n"
        "Další zákazy:\n"
        "- Neměň význam zdrojových informací.\n"
        "- Nespojuj tuto osobu s jinou osobou stejného nebo podobného jména.\n"
        "- Nepřidávej žádná data, místa ani souvislosti, pokud nejsou ve zdroji.\n"
        "- Nepiš, že osoba něco „pravděpodobně“, „zřejmě“ nebo „nejspíš“ udělala.\n"
        "- Nepoužívej obecné fráze, které vytvářejí falešný dojem významu, pokud to nevyplývá ze zdroje.\n"
        "- Nepřidávej bibliografii, odkazy, reference, poznámky pod čarou ani technické části Wikipedie."
    )


def _build_method_block(angle: dict[str, Any]) -> str:
    directive = angle.get("directive", "Drž se výhradně zdroje.")
    tone = angle.get("tone", "důstojný, čtivý")
    return (
        "Co máš udělat:\n"
        "- Přečti celý zdrojový text.\n"
        "- Zachovej všechny důležité životní události, fakta, díla, funkce, roky, místa a souvislosti.\n"
        "- Každou informaci přepiš vlastními slovy.\n"
        "- Vytvoř souvislé vyprávění místo suchého seznamu faktů.\n"
        f"- Režim generace: {directive}\n"
        f"- Cílový tón: {tone}.\n"
        "- Pokud zdroj nějakou informaci neobsahuje, nesmí se ve výsledku objevit."
    )


def _build_safety_block() -> str:
    return (
        "Bezpečnost proti halucinacím:\n"
        "Před odevzdáním interně zkontroluj každou větu:\n"
        "1. Je tato informace přímo obsažená ve zdroji?\n"
        "2. Neobsahuje věta nové tvrzení, které ve zdroji není?\n"
        "3. Nemůže být tato věta omylem vztažená k jiné osobě?\n"
        "4. Nezměnil jsem význam původní informace?\n"
        "5. Nezačíná text detailem, který ve zdroji patří až do pozdější části života nebo do posmrtné paměti?\n"
        "6. Neocitla se část „Památka“ nebo posmrtné připomínky omylem na začátku?\n\n"
        "Pokud některá věta nebo odstavec neprojde kontrolou, odstraň ho nebo ho přepiš tak, aby přesně odpovídal zdroji."
    )


def _build_edge_cases_block() -> str:
    return (
        "Pokud je zdroj příliš krátký:\n"
        "- Stále vrať použitelný životopisný text.\n"
        "- Nerozšiřuj ho vymyšlenými informacemi.\n"
        "- Raději napiš kratší bezpečný text než delší nepravdivý text.\n\n"
        "Pokud je osoba ve zdroji nejednoznačná:\n"
        "- Nemíchej více osob dohromady.\n"
        "- Použij pouze informace, které se jednoznačně vztahují k požadované osobě.\n"
        "- Pokud nelze osobu jednoznačně určit, napiš bezpečný obecný výtah pouze z jistých informací."
    )


def _build_output_block() -> str:
    return (
        "Výstup:\n"
        "- Vrať pouze finální biografický text.\n"
        "- Nepiš žádné vysvětlení.\n"
        "- Nepiš žádné poznámky o tom, že pracuješ se zdrojem.\n"
        "- Nepiš seznam použitých pravidel.\n"
        "- Nepoužívej markdown nadpisy.\n"
        "- Drž se rozsahu 300–700 slov.\n"
        "- Nikdy nepřekroč 700 slov."
    )


def build_system_prompt(angle: dict, style: str | None = None) -> str:
    profile = PROMPT_PROFILES["vkorni_memorial"]
    blocks = [
        "Jsi produkční biografický editor.",
        profile["intro"],
        _build_base_rules_block(),
        _build_method_block(angle),
        "Styl:\n" + _format_bullets(profile["style_rules"]),
        _build_structure_block(profile["section_template"]),
        "Pořadí a kompozice:\n" + _format_bullets(profile["ordering_rules"]),
        _build_safety_block(),
        _build_edge_cases_block(),
        _build_output_block(),
    ]

    if style:
        blocks.append(
            "Doplňkové omezení:\n"
            "- Případný stylový vzor ber jen jako rytmickou inspiraci.\n"
            "- Nesmíš z něj převzít žádná fakta ani nové významové vrstvy."
        )

    return "\n\n".join(blocks)


def build_user_message(context: str, angle: dict) -> str:
    person_name = _extract_person_name(context) or "{{PERSON_NAME}}"
    source_text = context.strip() if isinstance(context, str) else ""

    return (
        "POŽADOVANÁ OSOBA:\n"
        f"{person_name}\n\n"
        "ZDROJOVÝ TEXT:\n"
        f"{source_text}"
    )
