import os
import unittest

from app.services.wiki_service import fetch_person_from_wikipedia


RUN_INTEGRATION = os.getenv("RUN_INTEGRATION_TESTS") == "1"


@unittest.skipUnless(RUN_INTEGRATION, "Set RUN_INTEGRATION_TESTS=1 to run")
class WikiIntegrationTests(unittest.TestCase):
    def test_wiki_fetch(self):
        person = fetch_person_from_wikipedia("Владимир Высоцкий")
        self.assertIsNotNone(person)
        self.assertTrue(person.get("summary_text"))


if __name__ == "__main__":
    unittest.main()
