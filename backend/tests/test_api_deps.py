"""Tests for api/deps.py — validate_name, json_response."""
import pytest
from fastapi import HTTPException
from app.api.deps import is_probable_person_name, validate_name, validate_person_name, json_response


def test_validate_name_ok():
    assert validate_name("  Иван Петров  ") == "Иван Петров"


def test_validate_person_name_normalizes_comma_name():
    assert validate_person_name("  Пушкин,   Александр   Сергеевич ") == "Пушкин Александр Сергеевич"


def test_is_probable_person_name_accepts_normal_person():
    assert is_probable_person_name("Пушкин Александр Сергеевич") is True


def test_is_probable_person_name_rejects_category_like_entry():
    assert is_probable_person_name("Участники Гражданской войны в России (красные)»") is False


def test_validate_name_empty():
    with pytest.raises(HTTPException) as exc:
        validate_name("   ")
    assert exc.value.status_code == 400


def test_validate_name_too_long():
    with pytest.raises(HTTPException) as exc:
        validate_name("А" * 121)
    assert exc.value.status_code == 400


def test_validate_name_control_char():
    with pytest.raises(HTTPException) as exc:
        validate_name("Иван\x01Петров")
    assert exc.value.status_code == 400


def test_json_response_has_cors():
    resp = json_response({"key": "value"})
    assert resp.headers["access-control-allow-origin"] == "*"


def test_json_response_body():
    import json
    resp = json_response({"x": 1})
    assert json.loads(resp.body) == {"x": 1}
