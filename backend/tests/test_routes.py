import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app


class RoutesTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("app.api.routes.get_biography", return_value={"name": "A", "text": "T", "photos": []})
    def test_generate_uses_cache(self, get_bio_mock):
        response = self.client.post("/api/generate?name=A")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "T")
        get_bio_mock.assert_called_once()

    @patch("app.api.routes.fetch_person_from_wikipedia", return_value={"name": "A", "summary_text": "S", "birth": "1900", "death": "2000", "images": []})
    @patch("app.api.routes.get_style_context", return_value="STYLE")
    @patch("app.api.routes.generate_text", return_value="Long text here" * 50)
    @patch("app.api.routes.fetch_person_images")
    @patch("app.api.routes.get_photos_by_person", return_value=[])
    @patch("app.api.routes.set_biography")
    def test_generate_new(self, set_bio_mock, get_photos_mock, fetch_images_mock, gen_text_mock, style_mock, wiki_mock):
        response = self.client.post("/api/generate?name=A&FORCE_REGENERATE=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "A")
        self.assertTrue(gen_text_mock.called)
        set_bio_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
