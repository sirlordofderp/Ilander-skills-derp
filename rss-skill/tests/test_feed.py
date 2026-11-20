import importlib.util
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('feed',Path(__file__).parents[1]/'scripts/rss_atom.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

class TestFeeds(unittest.TestCase):
    def test_rss(self):
        t, rows=f.parse_feed(b'<rss version="2.0"><channel><title>My RSS</title><item><title>Hello</title><link>https://example.org/post</link><guid>123</guid><pubDate>Fri, 20 Nov 2026 00:00:00 GMT</pubDate></item></channel></rss>','https://example.org/feed')
        self.assertEqual((t,rows[0]['title'],rows[0]['guid']),('My RSS','Hello','123'))
    def test_atom(self):
        t, rows=f.parse_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"><title>News</title><entry><title>Discovery</title><id>urn:abc</id><link rel="alternate" href="/story"/><updated>2026-11-20T00:00:00Z</updated></entry></feed>','https://example.org/atom')
        self.assertEqual(rows[0]['url'],'https://example.org/story')
    def test_no_entities(self):
        with self.assertRaises(ValueError):f.parse_feed(b'<!DOCTYPE x [<!ENTITY hi "no">]><rss/>','https://example.org/')
    def test_ingest_prune_bookmarks(self):
        d=f.empty_db();f.add_feed(d,'https://example.org/rss');feed=d['feeds'][0]
        entries=[{'title':str(i),'url':f'https://example.org/{i}','guid':str(i),'published_at':None} for i in range(4)]
        self.assertEqual(f.ingest(d,feed,entries),4)
        self.assertEqual(f.ingest(d,feed,entries),0)
        d['entries'][0]['bookmarked']=True
        d['settings']['active_cap']=2
        self.assertEqual(f.prune(d),1)
        self.assertEqual(len(d['entries']),3)
        self.assertEqual(len(d['seen_ids']),1)
        self.assertEqual(f.ingest(d,feed,entries),0)
        d['entries'][1]['discovered_at']='2020-01-01T00:00:00Z'
        self.assertGreaterEqual(f.prune(d),1)
        self.assertTrue(any(e['bookmarked'] for e in d['entries']))
    def test_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data.json';d=f.empty_db();f.add_feed(d,'https://example.org/rss');f.save(path,d)
            self.assertEqual(len(f.load(path)['feeds']),1)
    def test_opml(self):
        self.assertEqual(f.opml_urls(b'<opml><body><outline xmlUrl="https://example.org/rss" /></body></opml>'),['https://example.org/rss'])

if __name__=='__main__':
    unittest.main()
