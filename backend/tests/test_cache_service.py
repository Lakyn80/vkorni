import unittest
from unittest.mock import patch

from app.services.cache_service import get_biography, set_biography, delete_biography, list_biographies


class CacheServiceTests(unittest.TestCase):
    @patch("app.services.cache_service.set_json")
    def test_set_biography(self, set_json_mock):
        set_biography("Test", "Hello", ["/static/photos/a.jpg"])
        set_json_mock.assert_called_once()
        args, _ = set_json_mock.call_args
        self.assertEqual(args[0], "Test")
        self.assertEqual(args[1]["text"], "Hello")
        self.assertEqual(args[1]["photos"], ["/static/photos/a.jpg"])

    @patch("app.services.cache_service.get_json", return_value={"name": "Test"})
    def test_get_biography(self, get_json_mock):
        result = get_biography("Test")
        self.assertEqual(result["name"], "Test")
        get_json_mock.assert_called_once_with("Test")

    @patch("app.services.cache_service.delete_key", return_value=True)
    def test_delete_biography(self, delete_mock):
        result = delete_biography("Test")
        self.assertTrue(result)
        delete_mock.assert_called_once_with("Test")

    @patch("app.services.cache_service.list_keys", return_value=["A", "B"])
    def test_list_biographies(self, list_mock):
        result = list_biographies()
        self.assertEqual(result, ["A", "B"])
        list_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
