import os
import sys
import tempfile
import unittest
import importlib


RUN_INTEGRATION = os.getenv("RUN_INTEGRATION_TESTS") == "1"


@unittest.skipUnless(RUN_INTEGRATION, "Set RUN_INTEGRATION_TESTS=1 to run")
class ChromaIntegrationTests(unittest.TestCase):
    def test_chroma_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["CHROMA_PATH"] = tmp
            if "app.db.chroma_client" in sys.modules:
                del sys.modules["app.db.chroma_client"]
            chroma = importlib.import_module("app.db.chroma_client")

            chroma.upsert_style("TestStyle", "Style text")
            style = chroma.get_style("TestStyle")
            self.assertEqual(style, "Style text")


if __name__ == "__main__":
    unittest.main()
