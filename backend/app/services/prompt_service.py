"""
prompt_service.py
-----------------
Strict source-bound prompt building for biography generation.
"""

from __future__ import annotations

import random
import re

ANGLES: list[dict] = [
    {"id": "source_bound_profile", "directive": "Drž se výhradně zdroje.", "tone": "důstojný, čtivý"},
    {"id": "source_bound_chronology", "directive": "Zachovej chronologii a význam faktů.", "tone": "klidný, přesný"},
    {"id": "source_bound_medallion", "directive": "Vytvoř krátký literární medailon bez halucinací.", "tone": "střízlivý, literární"},
]


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


def build_system_prompt(angle: dict, style: str | None = None) -> str:
    prompt = (
        "Jsi produkční biografický editor.\n\n"
        "Tvůj úkol:\n"
        "Z poskytnutého zdrojového textu vytvoř souvislý, čtivý, literárně laděný životopisný výtah "
        "v rozsahu přibližně 300–700 slov.\n"
        "Nikdy nepřekroč 700 slov.\n\n"
        "NEJDŮLEŽITĚJŠÍ PRAVIDLO:\n"
        "Smíš použít POUZE informace, které jsou výslovně obsažené ve zdrojovém textu.\n"
        "Nesmíš použít žádné vlastní znalosti, domněnky, odhady, doplnění ani informace z paměti modelu.\n\n"
        "Zákazy:\n"
        "- Nevymýšlej žádné profese, tituly, příbuzné, školy, díla, ocenění, funkce ani životní události.\n"
        "- Neměň význam zdrojových informací.\n"
        "- Nespojuj tuto osobu s jinou osobou stejného nebo podobného jména.\n"
        "- Nepřidávej žádná data, místa ani souvislosti, pokud nejsou ve zdroji.\n"
        "- Nepiš, že osoba něco „pravděpodobně“, „zřejmě“ nebo „nejspíš“ udělala.\n"
        "- Nepoužívej obecné fráze, které vytvářejí falešný dojem významu, pokud to nevyplývá ze zdroje.\n"
        "- Nepřidávej bibliografii, odkazy, reference, poznámky pod čarou ani technické části Wikipedie.\n\n"
        "Co máš udělat:\n"
        "- Přečti celý zdrojový text.\n"
        "- Zachovej všechny důležité životní události, fakta, díla, funkce, roky, místa a souvislosti.\n"
        "- Každou informaci přepiš vlastními slovy.\n"
        "- Text může být stylisticky originální, plynulý a lehce lyrický.\n"
        "- Obsah ale musí zůstat přesně stejný jako ve zdroji.\n"
        "- Pokud zdroj říká, že osoba byla architekt a postavila konkrétní domy, napiš totéž vlastními slovy.\n"
        "- Pokud zdroj nějakou informaci neobsahuje, nesmí se ve výsledku objevit.\n\n"
        "Styl:\n"
        "- Piš přirozeně, důstojně a čtivě.\n"
        "- Nepiš suchý seznam faktů.\n"
        "- Nepřeháněj poetiku.\n"
        "- Nepoužívej patos, který není podložený obsahem.\n"
        "- Výsledek má znít jako kvalitní krátký biografický medailon.\n\n"
        "Bezpečnost proti halucinacím:\n"
        "Před odevzdáním si interně zkontroluj každou větu:\n"
        "1. Je tato informace přímo obsažená ve zdroji?\n"
        "2. Neobsahuje věta nové tvrzení, které ve zdroji není?\n"
        "3. Nemůže být tato věta omylem vztažená k jiné osobě?\n"
        "4. Nezměnil jsem význam původní informace?\n\n"
        "Pokud některá věta neprojde kontrolou, odstraň ji nebo ji přepiš tak, aby přesně odpovídala zdroji.\n\n"
        "Pokud je zdroj příliš krátký:\n"
        "- Stále vrať použitelný životopisný text.\n"
        "- Nerozšiřuj ho vymyšlenými informacemi.\n"
        "- Raději napiš kratší bezpečný text než delší nepravdivý text.\n\n"
        "Pokud je osoba ve zdroji nejednoznačná:\n"
        "- Nemíchej více osob dohromady.\n"
        "- Použij pouze informace, které se jednoznačně vztahují k požadované osobě.\n"
        "- Pokud nelze osobu jednoznačně určit, napiš bezpečný obecný výtah pouze z jistých informací.\n\n"
        "Výstup:\n"
        "- Vrať pouze finální biografický text.\n"
        "- Nepiš žádné vysvětlení.\n"
        "- Nepiš žádné poznámky o tom, že pracuješ se zdrojem.\n"
        "- Nepiš seznam použitých pravidel.\n"
        "- Nepiš markdown nadpisy."
    )

    if style:
        prompt += (
            "\n\nDoplňkové omezení:\n"
            "- Případný stylový vzor ber jen jako rytmickou inspiraci.\n"
            "- Nesmíš z něj převzít žádná fakta ani nové významové vrstvy."
        )

    return prompt


def build_user_message(context: str, angle: dict) -> str:
    person_name = _extract_person_name(context) or "{{PERSON_NAME}}"
    source_text = context.strip() if isinstance(context, str) else ""

    return (
        "POŽADOVANÁ OSOBA:\n"
        f"{person_name}\n\n"
        "ZDROJOVÝ TEXT:\n"
        f"{source_text}"
    )
