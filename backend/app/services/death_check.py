from typing import Optional, Dict

def is_deceased(person_data: Optional[Dict]) -> bool:
    """
    NOVÁ 100% logika:
    Osoba je považována za zemřelou POUZE tehdy,
    pokud máme strukturované datum úmrtí z Wikidaty.
    """

    if not person_data:
        return False

    # Klíčové: bereme jen strukturované pole z wiki_service.py
    death_year = person_data.get("death")

    # Pokud máme rok úmrtí -> je to jisté
    if death_year:
        return True

    # Jinak NE
    return False


def extract_death_year(person_data: Dict) -> Optional[str]:
    """
    Vrací rok úmrtí, pokud existuje.
    """
    return person_data.get("death")
