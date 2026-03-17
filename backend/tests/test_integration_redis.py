import os
import unittest


RUN_INTEGRATION = os.getenv("RUN_INTEGRATION_TESTS") == "1"


@unittest.skipUnless(RUN_INTEGRATION, "Set RUN_INTEGRATION_TESTS=1 to run")
class RedisIntegrationTests(unittest.TestCase):
    def test_redis_roundtrip(self):
        from app.db.redis_client import set_json, get_json, delete_key

        key = "integration_test"
        set_json(key, {"ok": True})
        val = get_json(key)
        self.assertEqual(val["ok"], True)
        delete_key(key)


if __name__ == "__main__":
    unittest.main()
