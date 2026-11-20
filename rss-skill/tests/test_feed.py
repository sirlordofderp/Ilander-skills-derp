import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('feed', Path(__file__).parents[1] / 'scripts/rss_atom.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


class TestFeeds(unittest.TestCase):
    def test_rss(self):
        t, rows = f.parse_feed(b'<rss version="2.0"><channel><title>My RSS</title><item><title>Hello</title><link>https://example.org/post</link><guid>123</guid><pubDate>Fri, 20 Nov 2026 00:00:00 GMT</pubDate></item></channel></rss>', 'https://example.org/feed')
        self.assertEqual((t, rows[0]['title'], rows[0]['guid']), ('My RSS', 'Hello', '123'))


if __name__ == '__main__':
    unittest.main()
