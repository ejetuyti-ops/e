"""EJET Search: private, local-first search index.

Run with: python search_server.py
The server binds only to 127.0.0.1 and stores indexed pages in ejет_search.db.
No third-party search API or analytics are used.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import sqlite3
import threading
import webbrowser

HOST = "127.0.0.1"
PORT = 8765
DB_PATH = Path(__file__).with_name("ejet_search.db")
DB_LOCK = threading.Lock()


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            value = data.strip()
            if value:
                self.parts.append(value)


def connect_db():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    return db


def clean_text(value):
    return re.sub(r"\\s+", " ", value or "").strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "EJETSearch/0.1"

    def send_json(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/search":
            query = clean_text(parse_qs(parsed.query).get("q", [""])[0])
            if not query:
                return self.send_json(200, {"query": query, "results": []})
            terms = [term for term in query.split() if len(term) > 1][:8]
            where = " AND ".join(["(title LIKE ? OR content LIKE ?)"] * len(terms))
            params = []
            for term in terms:
                like = "%" + term + "%"
                params.extend([like, like])
            with DB_LOCK, connect_db() as db:
                rows = db.execute(
                    f"SELECT title, url, substr(content, 1, 260) AS excerpt FROM pages WHERE {where} ORDER BY added_at DESC LIMIT 30",
                    params,
                ).fetchall()
            return self.send_json(200, {
                "query": query,
                "results": [dict(row) for row in rows],
            })
        if parsed.path == "/api/stats":
            with DB_LOCK, connect_db() as db:
                count = db.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            return self.send_json(200, {"indexed_pages": count, "engine": "EJET Search"})
        if parsed.path in ("/", "/index.html"):
            page = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            return self.wfile.write(page)
        self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/index":
            return self.send_error(404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 1_000_000:
                return self.send_json(400, {"error": "Invalid request size"})
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            title = clean_text(data.get("title"))[:300]
            url = clean_text(data.get("url"))[:2000]
            content = clean_text(data.get("content"))[:200_000]
            if not title or not url or not content:
                return self.send_json(400, {"error": "title, url and content are required"})
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                return self.send_json(400, {"error": "Only http/https page URLs are accepted"})
            with DB_LOCK, connect_db() as db:
                db.execute(
                    "INSERT INTO pages(title, url, content) VALUES(?, ?, ?) "
                    "ON CONFLICT(url) DO UPDATE SET title=excluded.title, content=excluded.content, added_at=CURRENT_TIMESTAMP",
                    (title, url, content),
                )
            return self.send_json(201, {"indexed": True, "url": url})
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return self.send_json(400, {"error": "Invalid JSON request"})

    def log_message(self, fmt, *args):
        print("[EJET Search] " + (fmt % args))


PAGE = """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EJET Search</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#080d18;color:#e8eefc;font:16px Arial,sans-serif}
main{max-width:850px;margin:12vh auto;padding:24px}.brand{font-size:54px;font-weight:800;letter-spacing:-2px;color:#8abaff}
p{color:#9fb2cc}.search{display:flex;gap:10px;margin:28px 0}
input{flex:1;min-width:0;background:#101a2b;color:white;border:1px solid #385273;border-radius:14px;padding:17px;font-size:17px}
button{background:#2563eb;color:white;border:0;border-radius:12px;padding:0 22px;font-size:16px;cursor:pointer}
.result{padding:18px 0;border-bottom:1px solid #263751}.result a{color:#8abaff;font-size:19px;text-decoration:none}
.url{color:#70c49a;font-size:13px;margin:7px 0}.muted{font-size:13px;color:#8092ad}
</style><main><div class="brand">EJET</div><h1>Search</h1>
<p>Private local index. No external search provider. Results come only from pages you have indexed.</p>
<form class="search" id="form"><input id="q" placeholder="Search your EJET index…" autofocus><button>Search</button></form>
<div id="status" class="muted"></div><section id="results"></section>
<script>
const form=document.getElementById('form'),q=document.getElementById('q'),results=document.getElementById('results'),status=document.getElementById('status');
fetch('/api/stats').then(r=>r.json()).then(d=>status.textContent=d.indexed_pages+' pages in your local index.');
form.addEventListener('submit',async e=>{e.preventDefault();results.textContent='';status.textContent='Searching local index…';
const data=await fetch('/api/search?q='+encodeURIComponent(q.value)).then(r=>r.json());
status.textContent=data.results.length+' results in your local index.';
for(const item of data.results){const box=document.createElement('article');box.className='result';
const a=document.createElement('a');a.href=item.url;a.textContent=item.title;a.target='_blank';a.rel='noopener noreferrer';
const url=document.createElement('div');url.className='url';url.textContent=item.url;
const p=document.createElement('p');p.textContent=item.excerpt;
box.append(a,url,p);results.append(box)}
if(!data.results.length){const p=document.createElement('p');p.textContent='No matching indexed pages yet. The index is empty or has no match.';results.append(p)}
});
</script></main></html>"""


if __name__ == "__main__":
    with DB_LOCK:
        connect_db().close()
    print(f"EJET Search running at http://{HOST}:{PORT}")
    print("Local-only server. Stop with Ctrl+C.")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
