import unittest
from unittest.mock import patch

from app.services.wiki_service import fetch_person_from_wikipedia


class DummyResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def fake_get(url, headers=None, params=None, timeout=None):
    if "page/summary" in url:
        return DummyResponse({
            "title": "Test Person",
            "extract": "Summary text",
            "content_urls": {"desktop": {"page": "http://wiki"}},
        })
    if "action=query&prop=pageprops" in url:
        return DummyResponse({
            "query": {
                "pages": {
                    "1": {"pageprops": {"wikibase_item": "Q1"}}
                }
            }
        })
    if "wikidata" in url:
        return DummyResponse({
            "entities": {
                "Q1": {
                    "claims": {
                        "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+1970-01-01T00:00:00Z"}}}}],
                        "P570": [{"mainsnak": {"datavalue": {"value": {"time": "+2020-01-01T00:00:00Z"}}}}],
                    }
                }
            }
        })
    if params and params.get("prop") == "images":
        return DummyResponse({
            "query": {"pages": {"1": {"images": [{"title": "File:Test.jpg"}]}}}
        })
    if params and params.get("prop") == "imageinfo":
        return DummyResponse({
            "query": {"pages": {"1": {"imageinfo": [{"url": "http://example.com/Test.jpg", "extmetadata": {}}]}}}
        })
    return DummyResponse({})


class WikiServiceTests(unittest.TestCase):
    @patch("app.services.wiki_service.requests.get", side_effect=fake_get)
    def test_fetch_person_from_wikipedia(self, get_mock):
        person = fetch_person_from_wikipedia("Test Person")
        self.assertEqual(person["name"], "Test Person")
        self.assertEqual(person["summary_text"], "Summary text")
        self.assertEqual(person["birth"], "1970")
        self.assertEqual(person["death"], "2020")
        self.assertEqual(person["images"], ["http://example.com/Test.jpg"])


if __name__ == "__main__":
    unittest.main()
