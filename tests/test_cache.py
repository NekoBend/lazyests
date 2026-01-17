import shutil
import tempfile
import unittest
from pathlib import Path

from lazyests.cache import RequestCache
from lazyests.schemas import FetchResponseData


class TestRequestCache(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_cache.db"
        self.cache = RequestCache(self.db_path)

    def tearDown(self):
        self.cache.close()
        shutil.rmtree(self.test_dir)

    def test_validate_data_valid(self):
        data = {
            "status": 200,
            "statusText": "OK",
            "url": "http://example.com",
            "headers": {"Content-Type": "application/json"},
            "text": "{}",
            "redirected": False,
            "type": "basic",
        }
        validated = self.cache._validate_data(data)
        self.assertIsNotNone(validated)
        assert validated is not None  # for type checker
        self.assertEqual(validated["status"], 200)

    def test_validate_data_invalid_missing_key(self):
        data = {
            "status": 200,
            # Missing statusText
            "url": "http://example.com",
            "headers": {"Content-Type": "application/json"},
            "text": "{}",
            "redirected": False,
            "type": "basic",
        }
        validated = self.cache._validate_data(data)
        self.assertIsNone(validated)

    def test_validate_data_not_dict(self):
        validated = self.cache._validate_data("not a dict")
        self.assertIsNone(validated)

    def test_generate_key(self):
        key1 = self.cache.generate_key("GET", "http://example.com", None, None, None)
        key2 = self.cache.generate_key("GET", "http://example.com", None, None, None)
        self.assertEqual(key1, key2)

        key3 = self.cache.generate_key(
            "GET", "http://example.com", {"q": 1}, None, None
        )
        self.assertNotEqual(key1, key3)

    def test_set_and_get(self):
        data: FetchResponseData = {
            "status": 200,
            "statusText": "OK",
            "url": "http://example.com",
            "headers": {"Content-Type": "application/json"},
            "text": "{}",
            "redirected": False,
            "type": "basic",
        }
        key = self.cache.generate_key("GET", "http://example.com", None, None, None)
        self.cache.set(key, data, 60)

        cached_data = self.cache.get(key)
        self.assertIsNotNone(cached_data)
        assert cached_data is not None  # for type checker
        self.assertEqual(cached_data["url"], "http://example.com")

    def test_expired_cache(self):
        data: FetchResponseData = {
            "status": 200,
            "statusText": "OK",
            "url": "http://example.com",
            "headers": {"Content-Type": "application/json"},
            "text": "{}",
            "redirected": False,
            "type": "basic",
        }
        key = self.cache.generate_key("GET", "http://example.com", None, None, None)
        self.cache.set(key, data, -1)  # Already expired

        cached_data = self.cache.get(key)
        self.assertIsNone(cached_data)


if __name__ == "__main__":
    unittest.main()
