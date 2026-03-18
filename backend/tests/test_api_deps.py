"""Tests for api/deps.py — validate_name, json_response."""
import pytest
from fastapi import HTTPException
from app.api.deps import validate_name, json_response


def test_validate_name_ok():
    assert validate_name("  Иван Петров  ") == "Иван Петров"


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
