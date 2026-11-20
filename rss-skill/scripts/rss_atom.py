#!/usr/bin/env python3
"""Dependency-free RSS/Atom headline index for a sandboxed agent."""
import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

MAX_BYTES = 2_000_000
MAX_FEEDS = 200
MAX_REDIRECTS = 4
USER_AGENT = 'Omnisiah-RSSAtom/1.0 (+headline-only feed reader)'
NS_ATOM = '{http://www.w3.org/2005/Atom}'


def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')
def timestamp(s):
    if not s: return None
    try:
        d = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
        return d.replace(tzinfo=dt.timezone.utc) if d.tzinfo is None else d.astimezone(dt.timezone.utc)
    except (ValueError, TypeError): return None

def age_days(s, ref):
    d = timestamp(s)
    return (ref - d).total_seconds()/86400 if d else 0

def digest(s): return hashlib.sha256(s.encode('utf-8')).hexdigest()
def fail(message): raise ValueError(message)
def normalize_url(url):
    url = (url or '').strip()
    u = urllib.parse.urlsplit(url)
    if u.scheme.lower() not in ('http', 'https') or not u.hostname or u.username or u.password:
        fail('Only public http(s) URLs without credentials are supported')
    if len(url) > 4096: fail('URL too long')
    return urllib.parse.urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path or '/', u.query, ''))


def public_host(url):
    """Best-effort SSRF mitigation, checked before each request/redirect."""
    u = urllib.parse.urlsplit(normalize_url(url))
    host = (u.hostname or '').lower().rstrip('.')
    if host in ('localhost',) or host.endswith(('.localhost', '.local', '.internal')): fail('Local host blocked')
    if u.port not in (None, 80, 443): fail('Nonstandard port blocked')
    try: infos = socket.getaddrinfo(host, u.port or (443 if u.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    except OSError as e: fail(f'DNS resolution failed: {e}')
    if not infos: fail('No addresses resolved')
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global: fail(f'Non-public address blocked for {host}')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None

OPENER = urllib.request.build_opener(NoRedirect)

def http_get(url, etag=None, modified=None, max_bytes=MAX_BYTES):
    url = normalize_url(url)
    for _ in range(MAX_REDIRECTS+1):
        public_host(url)
        headers = {'User-Agent': USER_AGENT, 'Accept': 'application/atom+xml, application/rss+xml, application/xml, text/xml, text/html;q=0.5'}
        if etag: headers['If-None-Match'] = etag
        if modified: headers['If-Modified-Since'] = modified
        req = urllib.request.Request(url, headers=headers)
        try:
            with OPENER.open(req, timeout=15) as response:
                size = response.headers.get('Content-Length')
                if size and int(size) > max_bytes: fail('Response exceeds size limit')
                data = response.read(max_bytes+1)
                if len(data)>max_bytes: fail('Response exceeds size limit')
                return data, url, dict(response.headers.items()), False
        except urllib.error.HTTPError as e:
            if e.code == 304: return b'', url, {}, True
            if e.code in (301, 302, 303, 307, 308):
                location = e.headers.get('Location')
                if not location: fail('Redirect missing Location')
                url = normalize_url(urllib.parse.urljoin(url, location))
                etag, modified = None, None
                continue
            fail(f'HTTP {e.code}: {url}')
        except urllib.error.URLError as e: fail(f'Network error: {e.reason}')
    fail('Too many redirects')


def xml_root(data):
    if re.search(br'<!\s*(DOCTYPE|ENTITY)\b', data, flags=re.I): fail('DTD and entity declarations are forbidden')
    try: return ET.fromstring(data)
    except ET.ParseError as e: fail(f'Invalid XML: {e}')

def txt(el): return ''.join(el.itertext()).strip() if el is not None else ''
def childtext(el, name): return txt(el.find(name))
def parse_date(s):
    if not s: return None
    try: return parsedate_to_datetime(s).astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z')
    except (ValueError, TypeError, IndexError):
        d = timestamp(s)
        return d.isoformat().replace('+00:00','Z') if d else None


def parse_feed(data, base):
    root = xml_root(data)
    name = root.tag.split('}')[-1].lower()
    result = []
    if name == 'rss' or name == 'rdf':
        channel = root.find('channel') if name == 'rss' else root.find('{http://purl.org/rss/1.0/}channel')
        if channel is None: channel = root
        title = childtext(channel,'title') or childtext(channel,'{http://purl.org/rss/1.0/}title') or base
        items = root.findall('channel/item') if name == 'rss' else root.findall('{http://purl.org/rss/1.0/}item')
        for item in items:
            t = childtext(item,'title') or childtext(item,'{http://purl.org/rss/1.0/}title')
            link = childtext(item,'link') or childtext(item,'{http://purl.org/rss/1.0/}link')
            guid = childtext(item,'guid')
            pub = childtext(item,'pubDate') or childtext(item,'{http://purl.org/dc/elements/1.1/}date')
            result.append((t,link,guid,parse_date(pub)))
    elif root.tag == NS_ATOM+'feed':
        title = childtext(root, NS_ATOM+'title') or base
        for item in root.findall(NS_ATOM+'entry'):
            t = childtext(item,NS_ATOM+'title')
            links = item.findall(NS_ATOM+'link')
            candidate = next((l for l in links if l.get('rel','alternate') == 'alternate' and l.get('href')), None)
            link = candidate.get('href') if candidate is not None else ''
            guid = childtext(item, NS_ATOM+'id')
            pub = childtext(item, NS_ATOM+'published') or childtext(item, NS_ATOM+'updated')
            result.append((t,link,guid,parse_date(pub)))
    else: fail('Not a supported RSS 2.0, RSS 1.0, or Atom feed')
    cleaned = []
    for t,link,guid,pub in result:
        if not t or not link: continue
        try:
            absolute = normalize_url(urllib.parse.urljoin(base,link))
        except ValueError: continue
        cleaned.append({'title':re.sub(r'\s+',' ',t).strip()[:500], 'url':absolute,'guid':guid[:2048] if guid else None,'published_at':pub})
    return title[:250], cleaned


def discover(url):
    data, actual, headers, _ = http_get(url)
    try:
        title, entries = parse_feed(data,actual)
        return [{'url':actual,'title':title,'entries':len(entries)}]
    except ValueError: pass
    from html.parser import HTMLParser
    class Links(HTMLParser):
        def __init__(self): super().__init__(); self.urls=[]
        def handle_starttag(self,tag,attrs):
            if tag!='link': return
            a=dict(attrs)
            if 'alternate' in a.get('rel','').lower().split() and any(x in a.get('type','').lower() for x in ('rss+xml','atom+xml','application/xml')) and a.get('href'):
                try: self.urls.append(normalize_url(urllib.parse.urljoin(actual,a['href'])))
                except ValueError: pass
    p=Links(); p.feed(data.decode('utf-8', errors='replace'))
    return [{'url':u} for u in dict.fromkeys(p.urls)][:25]


def empty_db():
    return {'schema_version':1, 'updated_at':now(),'feeds':[], 'entries':[], 'seen_ids':[],
            'settings':{'unread_days':7,'reviewed_days':4,'active_cap':1000,'seen_cap':5000}}

def load(path):
    if not path.exists(): return empty_db()
    try: d=json.loads(path.read_text(encoding='utf-8'))
    except (ValueError,OSError) as e: fail(f'Cannot read index: {e}')
    if not isinstance(d,dict) or d.get('schema_version')!=1 or not all(isinstance(d.get(k),list) for k in ('feeds','entries','seen_ids')): fail('Unsupported or corrupt index')
    return d

def save(path,db):
    db['updated_at']=now()
    path.parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(db,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode()
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def feed_by_id(d,id): return next((f for f in d['feeds'] if f['id']==id or f['url']==id),None)
def add_feed(d,url,title=None):
    url=normalize_url(url)
    if len(d['feeds'])>=MAX_FEEDS: fail(f'Feed limit {MAX_FEEDS} reached')
    if any(f['url']==url for f in d['feeds']): return False
    fid=digest(url)[:16]
    d['feeds'].append({'id':fid,'url':url,'title':title or url,'enabled':True,'added_at':now(), 'last_checked_at':None,'etag':None,'last_modified':None,'last_error':None})
    return True

def ingest(d, f, entries):
    known={x['id'] for x in d['entries']} | {x['id'] for x in d['seen_ids']}
    added=0
    for e in entries:
        key=digest(f['id']+'\n'+(e['guid'] or e['url']))
        if key in known: continue
        d['entries'].append({'id':key,'feed_id':f['id'],'title':e['title'],'url':e['url'],'published_at':e['published_at'],
                             'discovered_at':now(),'reviewed_at':None,'bookmarked':False})
        known.add(key); added+=1
    return added

def prune(d):
    ref=dt.datetime.now(dt.timezone.utc)
    before=len(d['entries']); remain=[]; removed=[]
    for e in d['entries']:
        expiry=d['settings']['reviewed_days'] if e.get('reviewed_at') else d['settings']['unread_days']
        basis=e.get('reviewed_at') or e.get('discovered_at')
        if not e.get('bookmarked') and age_days(basis,ref)>=expiry: removed.append(e)
        else: remain.append(e)
    active=[e for e in remain if not e.get('bookmarked')]
    active.sort(key=lambda e:e.get('discovered_at') or '')
    overflow=max(0,len(active)-d['settings']['active_cap'])
    evict={e['id'] for e in active[:overflow]}
    if evict:
        removed += [e for e in remain if e['id'] in evict]
        remain=[e for e in remain if e['id'] not in evict]
    d['entries']=remain
    history={x['id']:x for x in d['seen_ids']}
    for e in removed: history[e['id']]={'id':e['id'],'removed_at':now()}
    d['seen_ids']=sorted(history.values(),key=lambda x:x['removed_at'])[-d['settings']['seen_cap']:]
    return before-len(remain)

def opml_urls(data):
    root=xml_root(data)
    if root.tag.lower()!='opml': fail('Not OPML')
    return [el.get('xmlUrl') for el in root.iter('outline') if el.get('xmlUrl')]

def main(argv=None):
    p=argparse.ArgumentParser(description='RSS/Atom headline collector; JSON stays local until you explicitly back it up.')
    p.add_argument('--db',default=os.getenv('RSS_ATOM_DB','./rss-atom-index.json'))
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('add',help='Subscribe to a feed URL');a.add_argument('url');a.add_argument('--title')
    a=sub.add_parser('discover',help='Find feed URLs advertised by a site');a.add_argument('url')
    a=sub.add_parser('import-opml');a.add_argument('path')
    sub.add_parser('feeds')
    for cmd in ('remove','enable','disable'):
        a=sub.add_parser(cmd);a.add_argument('feed_id')
    a=sub.add_parser('fetch');a.add_argument('--feed');a.add_argument('--limit',type=int,default=50)
    a=sub.add_parser('headlines');a.add_argument('--limit',type=int,default=30);a.add_argument('--unread',action='store_true');a.add_argument('--bookmarked',action='store_true')
    for cmd in ('review','unreview','bookmark','unbookmark'):
        a=sub.add_parser(cmd);a.add_argument('entry_id')
    sub.add_parser('prune');sub.add_parser('stats')
    a=sub.add_parser('config');a.add_argument('--unread-days',type=int);a.add_argument('--reviewed-days',type=int);a.add_argument('--active-cap',type=int);a.add_argument('--seen-cap',type=int)
    a=sub.add_parser('export-opml');a.add_argument('path')
    args=p.parse_args(argv);path=Path(args.db); d=load(path); dirty=False
    if args.command=='discover': out=discover(args.url)
    elif args.command=='add':
        dirty=add_feed(d,args.url,args.title);out={'added':dirty,'feed_url':normalize_url(args.url)}
    elif args.command=='import-opml':
        urls=opml_urls(Path(args.path).read_bytes()); n=0; bad=[]
        for url in urls:
            try: n+=int(add_feed(d,url))
            except ValueError as e: bad.append({'url':url,'error':str(e)})
        dirty=bool(n);out={'added':n,'rejected':bad}
    elif args.command=='feeds': out=d['feeds']
    elif args.command in ('remove','enable','disable'):
        f=feed_by_id(d,args.feed_id)
        if f is None: fail('Feed not found')
        if args.command=='remove':
            d['feeds'].remove(f); dirty=True;out={'removed':f['url'],'headlines_retained':True}
        else: f['enabled']=args.command=='enable';dirty=True;out={'id':f['id'],'enabled':f['enabled']}
    elif args.command=='fetch':
        if not (1<=args.limit<=1000): fail('--limit must be 1..1000')
        targets=[feed_by_id(d,args.feed)] if args.feed else [f for f in d['feeds'] if f['enabled']]
        if not targets or None in targets: fail('No matching feed')
        results=[]
        for f in targets:
            if not f['enabled']: continue
            try:
                data,actual,headers,unchanged=http_get(f['url'],f.get('etag'),f.get('last_modified'))
                count=0
                if not unchanged:
                    title,parsed=parse_feed(data,actual)
                    f['title']=title
                    count=ingest(d,f,parsed[:args.limit])
                    f['etag']=headers.get('ETag') or headers.get('Etag')
                    f['last_modified']=headers.get('Last-Modified')
                f['last_checked_at']=now(); f['last_error']=None
                results.append({'feed':f['url'],'new':count,'not_modified':unchanged})
            except (ValueError, OSError) as e:
                f['last_error']=str(e)[:300];f['last_checked_at']=now()
                results.append({'feed':f['url'],'error':f['last_error']})
            dirty=True
        removed=prune(d);out={'results':results,'pruned':removed}
    elif args.command=='headlines':
        if args.limit<1 or args.limit>1000: fail('--limit must be 1..1000')
        items=d['entries']
        if args.unread: items=[e for e in items if not e.get('reviewed_at')]
        if args.bookmarked: items=[e for e in items if e.get('bookmarked')]
        out=sorted(items,key=lambda e:e.get('discovered_at') or '',reverse=True)[:args.limit]
    elif args.command in ('review','unreview','bookmark','unbookmark'):
        e=next((e for e in d['entries'] if e['id']==args.entry_id or e['id'].startswith(args.entry_id)),None)
        if not e: fail('Headline not found')
        if args.command in ('review','unreview'):e['reviewed_at']=now() if args.command=='review' else None
        else:e['bookmarked']=args.command=='bookmark'
        dirty=True;out={'id':e['id'],'reviewed_at':e['reviewed_at'],'bookmarked':e['bookmarked']}
    elif args.command=='prune':dirty=True;out={'removed':prune(d)}
    elif args.command=='stats':out={'feeds':len(d['feeds']),'enabled_feeds':sum(f['enabled'] for f in d['feeds']),'headlines':len(d['entries']),'bookmarks':sum(e['bookmarked'] for e in d['entries']),'seen_ids':len(d['seen_ids']),'sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None}
    elif args.command=='config':
        for cli,k in [('unread_days','unread_days'),('reviewed_days','reviewed_days'),('active_cap','active_cap'),('seen_cap','seen_cap')]:
            v=getattr(args,cli)
            if v is not None:
                if v<1 or v>100000:fail('Config value out of range')
                d['settings'][k]=v;dirty=True
        out=d['settings']
    elif args.command=='export-opml':
        from xml.sax.saxutils import escape, quoteattr
        lines=['<?xml version="1.0" encoding="UTF-8"?>','<opml version="2.0"><head><title>Omnisiah Feeds</title></head><body>']
        for f in d['feeds']:lines.append(f'<outline type="rss" text={quoteattr(f["title"])} xmlUrl={quoteattr(f["url"])}/>')
        lines.append('</body></opml>')
        Path(args.path).write_text('\n'.join(lines),encoding='utf-8');out={'exported':len(d['feeds']),'path':args.path}
    if dirty: save(path,d)
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError) as e:print(json.dumps({'error':str(e)}),file=sys.stderr);sys.exit(2)
