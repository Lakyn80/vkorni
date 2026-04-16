import os
import unittest
from unittest.mock import patch
import requests

from app.services.deepseek_service import generate_text, DeepSeekBillingError


class DummyResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "Generated"}}]}


class BillingResponse:
    status_code = 402

    def raise_for_status(self):
        raise requests.HTTPError("402 Client Error: Payment Required", response=self)

    def json(self):
        return {"error": {"message": "Insufficient Balance"}}


class DeepseekServiceTests(unittest.TestCase):
    @patch("app.services.deepseek_service.requests.post", return_value=DummyResponse())
    def test_generate_text(self, post_mock):
        os.environ["DEEPSEEK_KEY"] = "test"
        text, angle_id = generate_text("context", "style")
        self.assertEqual(text, "Generated")
        self.assertIsInstance(angle_id, str)
        self.assertTrue(post_mock.called)

    @patch("app.services.deepseek_service.requests.post", return_value=BillingResponse())
    def test_generate_text_raises_billing_error_on_402(self, post_mock):
        os.environ["DEEPSEEK_KEY"] = "test"
        with self.assertRaises(DeepSeekBillingError):
            generate_text("context", "style")
        self.assertTrue(post_mock.called)


if __name__ == "__main__":
    unittest.main()
