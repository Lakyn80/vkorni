import os
import sys
import tempfile
import unittest
import importlib


class PhotosRepoTests(unittest.TestCase):
    def test_add_and_get_photos(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "photos.db")
            os.environ["PHOTOS_DB_PATH"] = db_path

            if "app.db.photos_repo" in sys.modules:
                del sys.modules["app.db.photos_repo"]
            repo = importlib.import_module("app.db.photos_repo")

            repo.add_photo("Test", "/static/photos/Test/1.jpg", "http://src", "desc")
            photos = repo.get_photos_by_person("Test")
            self.assertEqual(len(photos), 1)
            self.assertEqual(photos[0]["file_path"], "/static/photos/Test/1.jpg")


if __name__ == "__main__":
    unittest.main()
