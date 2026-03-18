"""Tests for services/uniqueness_service.py."""
import pytest
from app.services.uniqueness_service import jaccard_similarity, is_unique_enough


def test_identical_texts_similarity_is_one():
    text = "Владимир Высоцкий был великим поэтом и актёром советской эпохи"
    assert jaccard_similarity(text, text) == pytest.approx(1.0)


def test_completely_different_texts_similarity_is_zero():
    a = "кот сидел на подоконнике и смотрел на улицу"
    b = "самолёт летел над горами со скоростью звука"
    sim = jaccard_similarity(a, b)
    assert sim == pytest.approx(0.0, abs=0.05)


def test_partial_overlap():
    a = "Яшин был великим вратарём советского футбола"
    b = "Яшин великий вратарь и легенда советского спорта"
    sim = jaccard_similarity(a, b)
    assert 0.1 < sim < 0.9


def test_empty_texts():
    assert jaccard_similarity("", "") == pytest.approx(0.0)
    assert jaccard_similarity("текст", "") == pytest.approx(0.0)


def test_is_unique_enough_different_texts():
    source = "краткое описание человека из Википедии " * 10
    generated = "совершенно иной взгляд на биографию этого деятеля " * 10
    assert is_unique_enough(generated, source) is True


def test_is_unique_enough_copy_is_not_unique():
    source = "Лев Яшин родился в Москве и стал великим футбольным вратарём " * 10
    assert is_unique_enough(source, source) is False


def test_is_unique_enough_custom_threshold():
    a = "тест уникальность проверка " * 5
    b = "тест уникальность проверка дополнение " * 5
    # very strict threshold — should fail
    assert is_unique_enough(a, b, threshold=0.01) is False
    # very loose threshold — should pass
    assert is_unique_enough(a, b, threshold=0.99) is True
