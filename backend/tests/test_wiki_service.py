import os
import tempfile
import unittest
from unittest.mock import patch

from app.services import wiki_service
from app.services.wiki_service import fetch_person_from_wikipedia


class DummyResponse:
    def __init__(self, data, status_code=200, headers=None):
        self._data = data
        self.status_code = status_code
        self.headers = headers or {}
        self.closed = False

    def json(self):
        return self._data

    def close(self):
        self.closed = True

    def iter_content(self, chunk_size=8192):
        yield b"image-bytes"


class FakeRedisClient:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def eval(self, script, numkeys, key, ttl_seconds):
        self.calls.append((key, ttl_seconds))
        return self.results.pop(0)


def fake_request_wikimedia_json(url, headers=None, params=None, timeout=None, purpose=None):
    if "page/summary" in url:
        return {
            "title": "Test Person",
            "extract": "Summary text",
            "content_urls": {"desktop": {"page": "http://wiki"}},
            "originalimage": {"source": "http://example.com/Test.jpg"},
        }
    if "action=query&prop=pageprops" in url:
        return {
            "query": {
                "pages": {
                    "1": {"pageprops": {"wikibase_item": "Q1"}}
                }
            }
        }
    if "wikidata" in url:
        return {
            "entities": {
                "Q1": {
                    "claims": {
                        "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+1970-01-01T00:00:00Z"}}}}],
                        "P570": [{"mainsnak": {"datavalue": {"value": {"time": "+2020-01-01T00:00:00Z"}}}}],
                    }
                }
            }
        }
    if params and params.get("prop") == "images":
        return {
            "query": {"pages": {"1": {"images": [{"title": "File:Test.jpg"}]}}}
        }
    if params and params.get("prop") == "imageinfo":
        return {
            "query": {"pages": {"1": {"imageinfo": [{"url": "http://example.com/Test.jpg", "extmetadata": {}}]}}}
        }
    return {}


class WikiServiceTests(unittest.TestCase):
    @patch("app.services.wiki_service._request_wikimedia_json", side_effect=fake_request_wikimedia_json)
    def test_fetch_person_from_wikipedia(self, request_json_mock):
        person = fetch_person_from_wikipedia("Test Person")
        self.assertEqual(person["name"], "Test Person")
        self.assertEqual(person["summary_text"], "Summary text")
        self.assertEqual(person["birth"], "1970")
        self.assertEqual(person["death"], "2020")
        self.assertEqual(person["images"], ["http://example.com/Test.jpg"])

    @patch("app.services.wiki_service.time.sleep")
    @patch("app.services.wiki_service.time.time", side_effect=[100.2, 100.2, 101.05])
    @patch.object(wiki_service.settings, "wiki_rate_limit_per_sec", 1)
    def test_wait_for_wiki_rate_limit_blocks_until_next_window(self, time_mock, sleep_mock):
        fake_client = FakeRedisClient([2, 1])

        with patch("app.services.wiki_service._get_wiki_rate_limit_redis", return_value=fake_client):
            wiki_service.wait_for_wiki_rate_limit()

        self.assertEqual(fake_client.calls[0], ("wiki_rate_limit:100", 2))
        self.assertEqual(fake_client.calls[1], ("wiki_rate_limit:101", 2))
        self.assertAlmostEqual(sleep_mock.call_args_list[0].args[0], 0.8, places=2)

    @patch("app.services.wiki_service._log_wiki_rate_limit_backend_failure")
    @patch("app.services.wiki_service.time.sleep")
    def test_wait_for_wiki_rate_limit_falls_back_when_redis_fails(self, sleep_mock, log_mock):
        with patch("app.services.wiki_service._get_wiki_rate_limit_redis", side_effect=RuntimeError("redis down")):
            wiki_service.wait_for_wiki_rate_limit()

        log_mock.assert_called_once()
        sleep_mock.assert_not_called()

    @patch("app.services.wiki_service.wait_for_wiki_rate_limit")
    @patch("app.services.wiki_service._throttle_wikimedia_request")
    @patch("app.services.wiki_service.time.sleep")
    @patch.object(wiki_service.settings, "wiki_request_max_retries", 3)
    @patch.object(wiki_service.settings, "wiki_request_backoff_seconds", 1.0)
    @patch.object(wiki_service.settings, "wiki_rate_limit_backoff_seconds", 5.0)
    def test_request_wikimedia_retries_429(self, sleep_mock, throttle_mock, rate_limit_mock):
        first = DummyResponse({}, status_code=429, headers={"Retry-After": "7"})
        second = DummyResponse({}, status_code=200)

        with patch.object(wiki_service._WIKIMEDIA_SESSION, "get", side_effect=[first, second]) as get_mock:
            response = wiki_service._request_wikimedia(
                "https://upload.wikimedia.org/test.jpg",
                headers=wiki_service.IMAGE_HEADERS,
                purpose="image download",
            )

        self.assertIs(response, second)
        self.assertEqual(get_mock.call_count, 2)
        sleep_mock.assert_called_once_with(7.0)
        self.assertEqual(rate_limit_mock.call_count, 2)

    @patch("app.services.wiki_service.wait_for_wiki_rate_limit")
    @patch("app.services.wiki_service._throttle_wikimedia_request")
    @patch("app.services.wiki_service.time.sleep")
    @patch.object(wiki_service.settings, "wiki_request_max_retries", 4)
    @patch.object(wiki_service.settings, "wiki_request_backoff_seconds", 1.0)
    def test_request_wikimedia_retries_5xx_with_exponential_backoff(self, sleep_mock, throttle_mock, rate_limit_mock):
        responses = [
            DummyResponse({}, status_code=503),
            DummyResponse({}, status_code=502),
            DummyResponse({}, status_code=200),
        ]

        with patch.object(wiki_service._WIKIMEDIA_SESSION, "get", side_effect=responses) as get_mock:
            response = wiki_service._request_wikimedia(
                "https://upload.wikimedia.org/test.jpg",
                headers=wiki_service.IMAGE_HEADERS,
                purpose="image download",
            )

        self.assertIs(response, responses[-1])
        self.assertEqual(get_mock.call_count, 3)
        self.assertEqual(sleep_mock.call_args_list[0].args[0], 1.0)
        self.assertEqual(sleep_mock.call_args_list[1].args[0], 2.0)
        self.assertEqual(rate_limit_mock.call_count, 3)

    @patch("app.services.wiki_service.wait_for_wiki_rate_limit")
    @patch("app.services.wiki_service._throttle_wikimedia_request")
    @patch("app.services.wiki_service.time.sleep")
    @patch.object(wiki_service.settings, "wiki_request_max_retries", 5)
    def test_request_wikimedia_does_not_retry_403(self, sleep_mock, throttle_mock, rate_limit_mock):
        forbidden = DummyResponse({}, status_code=403)

        with patch.object(wiki_service._WIKIMEDIA_SESSION, "get", return_value=forbidden) as get_mock:
            response = wiki_service._request_wikimedia(
                "https://upload.wikimedia.org/test.jpg",
                headers=wiki_service.IMAGE_HEADERS,
                purpose="image download",
            )

        self.assertIsNone(response)
        self.assertEqual(get_mock.call_count, 1)
        sleep_mock.assert_not_called()
        rate_limit_mock.assert_called_once()

    def test_fetch_person_images_reuses_cached_download_by_source_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            cached_rel_path = "/static/photos/shared/cached.webp"
            cached_file = os.path.join(tmp, "shared", "cached.webp")
            os.makedirs(os.path.dirname(cached_file), exist_ok=True)
            with open(cached_file, "wb") as fh:
                fh.write(b"cached")

            with patch.object(wiki_service, "STATIC_PHOTOS_DIR", tmp), \
                 patch.object(wiki_service, "MAX_IMAGES", 1), \
                 patch("app.services.wiki_service._safe_search_wiki_title", return_value="Test Person"), \
                 patch("app.services.wiki_service._request_wikimedia_json", return_value={"originalimage": {"source": "https://upload.wikimedia.org/Test.jpg"}}), \
                 patch("app.services.wiki_service.find_photo_by_source_url", return_value={"file_path": cached_rel_path}), \
                 patch("app.services.wiki_service._relative_static_to_abs_path", return_value=cached_file), \
                 patch("app.services.wiki_service._download_wikimedia_image") as download_mock, \
                 patch("app.services.wiki_service.add_photo") as add_photo_mock:
                images = wiki_service.fetch_person_images("Test Person")

        self.assertEqual(images, [{
            "file_path": cached_rel_path,
            "source_url": "https://upload.wikimedia.org/Test.jpg",
            "description": None,
        }])
        download_mock.assert_not_called()
        add_photo_mock.assert_called_once_with("Test Person", cached_rel_path, "https://upload.wikimedia.org/Test.jpg", None)


if __name__ == "__main__":
    unittest.main()
