import os
import unittest
from unittest.mock import patch

from app.services.deepseek_service import generate_text


class DummyResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "Generated"}}]}


class DeepseekServiceTests(unittest.TestCase):
    @patch("app.services.deepseek_service.requests.post", return_value=DummyResponse())
    def test_generate_text(self, post_mock):
        os.environ["DEEPSEEK_KEY"] = "test"
        result = generate_text("context", "style")
        self.assertEqual(result, "Generated")
        self.assertTrue(post_mock.called)


if __name__ == "__main__":
    unittest.main()
