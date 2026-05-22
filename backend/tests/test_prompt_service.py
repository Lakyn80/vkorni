from app.services.prompt_service import ANGLES, build_system_prompt, build_user_message, pick_angle


def test_pick_angle_returns_known_angle():
    angle = pick_angle()
    assert angle in ANGLES


def test_build_system_prompt_is_creative_but_strictly_source_bound():
    prompt = build_system_prompt(ANGLES[0], style="ритм без фактов")

    assert "ТВОРЧЕСКАЯ РАМКА" in prompt
    assert "ОБЯЗАТЕЛЬНАЯ СТРУКТУРА" in prompt
    assert "Запрещено что-либо выдумывать" in prompt
    assert "Запрещено придумывать чувства, мысли, мотивы" in prompt
    assert "Запрещены гипотетические конструкции" in prompt
    assert "Если выбранный угол зрения требует фактов, которых нет" in prompt
    assert "эмодзи-заголовки" in prompt


def test_build_user_message_requires_skipping_unsupported_sections():
    message = build_user_message("Факт 1", ANGLES[0])

    assert "не дополняй факты" in message
    assert "пропусти этот раздел" in message
    assert "Подтвержденные данные" in message
