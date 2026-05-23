from app.services.prompt_service import ANGLES, build_system_prompt, build_user_message, pick_angle


def test_pick_angle_returns_known_angle():
    angle = pick_angle()
    assert angle in ANGLES


def test_build_system_prompt_matches_strict_source_only_contract():
    prompt = build_system_prompt(ANGLES[0], style="ритм без фактов")

    assert "Jsi produkční biografický editor." in prompt
    assert "Napiš biografii pro pamětní projekt" in prompt
    assert "Smíš použít POUZE informace" in prompt
    assert "Nesmíš použít žádné vlastní znalosti" in prompt
    assert "Nepiš jako Wikipedie." in prompt
    assert "Památka" in prompt
    assert "Nezačínej text náhodným detailem z konce článku." in prompt
    assert "Bezpečnost proti halucinacím" in prompt
    assert "Nikdy nepřekroč 700 slov." in prompt
    assert "Vrať pouze finální biografický text." in prompt


def test_build_user_message_includes_person_name_and_source_text():
    context = "Полное имя: Юрий Гагарин\nДата рождения: 9 марта 1934\nПолный подтвержденный текст источника:\nФакт 1"
    message = build_user_message(context, ANGLES[0])

    assert "POŽADOVANÁ OSOBA:" in message
    assert "Юрий Гагарин" in message
    assert "ZDROJOVÝ TEXT:" in message
    assert "Факт 1" in message
