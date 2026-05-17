import os
import unittest
from unittest.mock import patch

import httpx

from app.services.deepseek_service import (
    DEEPSEEK_URL,
    DeepSeekBillingError,
    DeepSeekServiceError,
    generate_text,
)


class DummyResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "Generated"}}]}


class EmptyResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": ""}}]}


def _http_status_error(status_code: int, payload: dict) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", DEEPSEEK_URL)
    response = httpx.Response(status_code=status_code, json=payload, request=request)
    return httpx.HTTPStatusError("HTTP status error", request=request, response=response)


class DeepseekServiceTests(unittest.TestCase):
    @patch("app.services.deepseek_service.httpx.post", return_value=DummyResponse())
    def test_generate_text(self, post_mock):
        os.environ["DEEPSEEK_KEY"] = "test"
        text, angle_id = generate_text("context", "style")
        self.assertEqual(text, "Generated")
        self.assertIsInstance(angle_id, str)
        self.assertTrue(post_mock.called)

    @patch(
        "app.services.deepseek_service.httpx.post",
        side_effect=_http_status_error(402, {"error": {"message": "Insufficient Balance"}}),
    )
    def test_generate_text_raises_billing_error_on_402(self, post_mock):
        os.environ["DEEPSEEK_KEY"] = "test"
        with self.assertRaises(DeepSeekBillingError):
            generate_text("context", "style")
        self.assertTrue(post_mock.called)

    @patch(
        "app.services.deepseek_service.httpx.post",
        side_effect=httpx.ConnectError("tls failed", request=httpx.Request("POST", DEEPSEEK_URL)),
    )
    def test_generate_text_raises_service_error_on_request_error(self, post_mock):
        os.environ["DEEPSEEK_KEY"] = "test"
        with self.assertRaises(DeepSeekServiceError):
            generate_text("context", "style")
        self.assertTrue(post_mock.called)

    @patch("app.services.deepseek_service.httpx.post", return_value=EmptyResponse())
    def test_generate_text_raises_service_error_on_empty_response(self, post_mock):
        os.environ["DEEPSEEK_KEY"] = "test"
        with self.assertRaises(DeepSeekServiceError):
            generate_text("context", "style")
        self.assertTrue(post_mock.called)


if __name__ == "__main__":
    unittest.main()
