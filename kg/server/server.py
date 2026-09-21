#!/usr/bin/env python3
"""TWK knowledge-graph authoring server. Stdlib only."""

from __future__ import annotations

import json
import re
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from twk_lib import context_at, graph_of, merge_docs, validate

HERE = Path(__file__).resolve().parent
REPO = HERE.parent / "repo"
STATIC = HERE / "static"
AA = HERE.parent / "american-alchemy"

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def repo_files():
    REPO.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(REPO.glob("*.twk")) + sorted(REPO.glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            out.append({"file": p.name, "error": str(e)})
            continue
        out.append(
            {
                "file": p.name,
                "id": doc.get("id"),
                "kind": doc.get("kind") or "document",
                "title": doc.get("title") or doc.get("id"),
                "media": (doc.get("media") or {}).get("uri"),
                "entities": len(doc.get("entities") or []),
                "claims": len(doc.get("claims") or []),
                "relations": len(doc.get("relations") or []),
                "chapters": len(((doc.get("structure") or {}).get("chapters")) or []),
                "timeline": len(doc.get("timeline") or []),
            }
        )
    return out


def read_doc(name: str) -> dict:
    if not SAFE_NAME.match(name):
        raise ValueError("unsafe filename")
    path = REPO / name
    if not path.exists():
        raise FileNotFoundError(name)
    return json.loads(path.read_text(encoding="utf-8"))


def write_doc(name: str, doc: dict) -> None:
    if not SAFE_NAME.match(name):
        raise ValueError("unsafe filename")
    if not name.endswith(".twk") and not name.endswith(".json"):
        name = name + ".twk"
    path = REPO / name
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    twin = AA / name
    if name.startswith("drumm-pyramids") and AA.exists():
        twin.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")


def compose(doc: dict) -> dict:
    comp = doc.get("composition") or {}
    dict_ref = (comp.get("dictionary") or {}).get("uri")
    if not dict_ref:
        return doc
    name = Path(dict_ref).name
    cand = REPO / name
    if not cand.exists():
        cand = AA / name
    if not cand.exists():
        return doc
    dictionary = json.loads(cand.read_text(encoding="utf-8"))
    return merge_docs(doc, dictionary)


class Handler(BaseHTTPRequestHandler):
    server_version = "TWK-KG/0.2"

    def log_message(self, fmt, *args):
        print(f"[kg] {self.address_string()} {fmt % args}")

    def _send(self, code: int, body, content_type="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            raw = json.dumps(body, indent=2, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            raw = body.encode("utf-8")
        else:
            raw = body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            self._get()
        except FileNotFoundError as e:
            self._send(404, {"error": str(e)})
        except Exception:
            self._send(500, {"error": traceback.format_exc()})

    def do_PUT(self):
        self._mutate("PUT")

    def do_POST(self):
        self._mutate("POST")

    def do_DELETE(self):
        try:
            parsed = urlparse(self.path)
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) == 3 and parts[0] == "api" and parts[1] == "docs":
                name = unquote(parts[2])
                if not SAFE_NAME.match(name):
                    return self._send(400, {"error": "unsafe filename"})
                path = REPO / name
                if not path.exists():
                    return self._send(404, {"error": name})
                path.unlink()
                return self._send(200, {"ok": True, "deleted": name})
            self._send(404, {"error": "not found"})
        except Exception:
            self._send(500, {"error": traceback.format_exc()})

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def _get(self):
        parsed = urlparse(self.path)
        path = parsed.path
        q = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        if path in ("/", "/admin", "/admin/"):
            html = (STATIC / "admin.html").read_text(encoding="utf-8")
            return self._send(200, html, "text/html; charset=utf-8")

        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            fp = STATIC / rel
            if not fp.exists() or not fp.is_file():
                return self._send(404, {"error": rel})
            ctype = "text/css" if rel.endswith(".css") else "application/javascript"
            return self._send(200, fp.read_text(encoding="utf-8"), ctype)

        if path == "/api/docs":
            return self._send(200, repo_files())

        parts = [p for p in path.split("/") if p]
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "docs":
            name = unquote(parts[2])
            doc = read_doc(name)
            return self._send(200, {"file": name, "doc": doc, "report": validate(doc)})

        if path == "/api/compose":
            name = q.get("file")
            if not name:
                return self._send(400, {"error": "file required"})
            doc = compose(read_doc(name))
            return self._send(200, {"file": name, "doc": doc, "report": validate(doc)})

        if path == "/api/graph":
            name = q.get("file")
            if not name:
                return self._send(400, {"error": "file required"})
            doc = compose(read_doc(name))
            return self._send(200, graph_of(doc))

        if path == "/api/context":
            name = q.get("file")
            t = float(q.get("t") or 0)
            if not name:
                return self._send(400, {"error": "file required"})
            doc = compose(read_doc(name))
            return self._send(200, context_at(doc, t))

        if path == "/api/validate":
            name = q.get("file")
            if not name:
                return self._send(400, {"error": "file required"})
            return self._send(200, validate(read_doc(name)))

        if path == "/api/health":
            return self._send(200, {"ok": True, "repo": str(REPO), "files": len(repo_files())})

        self._send(404, {"error": "not found", "path": path})

    def _mutate(self, method: str):
        try:
            parsed = urlparse(self.path)
            parts = [p for p in parsed.path.split("/") if p]
            body = self._body()
            if method == "POST" and parsed.path == "/api/validate":
                return self._send(200, validate(body.get("doc") or body))
            if method == "POST" and parsed.path == "/api/docs":
                name = body.get("file")
                doc = body.get("doc")
                if not name or not doc:
                    return self._send(400, {"error": "file and doc required"})
                write_doc(name, doc)
                return self._send(201, {"ok": True, "file": name, "report": validate(doc)})
            if method == "PUT" and len(parts) == 3 and parts[0] == "api" and parts[1] == "docs":
                name = unquote(parts[2])
                doc = body.get("doc") if "doc" in body else body
                write_doc(name, doc)
                return self._send(200, {"ok": True, "file": name, "report": validate(doc)})
            if method == "POST" and parsed.path == "/api/patch":
                name = body.get("file")
                collection = body.get("collection")
                item = body.get("item")
                if not name or not collection or not item:
                    return self._send(400, {"error": "file, collection, item required"})
                doc = read_doc(name)
                arr = list(doc.get(collection) or [])
                idx = next((i for i, x in enumerate(arr) if x.get("id") == item.get("id")), None)
                if idx is None:
                    arr.append(item)
                else:
                    arr[idx] = item
                doc[collection] = arr
                write_doc(name, doc)
                return self._send(200, {"ok": True, "file": name, "report": validate(doc), "doc": doc})
            self._send(404, {"error": "not found"})
        except Exception:
            self._send(500, {"error": traceback.format_exc()})


def main():
    REPO.mkdir(parents=True, exist_ok=True)
    STATIC.mkdir(parents=True, exist_ok=True)
    host, port = "0.0.0.0", 8765
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"TWK KG server http://127.0.0.1:{port}/admin  repo={REPO}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
