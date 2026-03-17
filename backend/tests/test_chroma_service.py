import unittest
from unittest.mock import patch

from app.services.chroma_service import get_style_context


class ChromaServiceTests(unittest.TestCase):
    @patch("app.services.chroma_service.get_style", return_value="STYLE")
    def test_get_style_context_exact(self, get_style_mock):
        result = get_style_context("Any")
        self.assertEqual(result, "STYLE")
        get_style_mock.assert_called_once_with("Any")

    @patch("app.services.chroma_service.search_styles", return_value=[{"text": "A"}, {"text": "B"}])
    @patch("app.services.chroma_service.get_style", return_value=None)
    def test_get_style_context_fallback(self, get_style_mock, search_mock):
        result = get_style_context("Missing", top_k=3)
        self.assertEqual(result, "A\nB")
        search_mock.assert_called_once_with("Missing", top_k=3)


if __name__ == "__main__":
    unittest.main()
