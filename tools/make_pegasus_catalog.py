#!/usr/bin/env python3
"""
Crawl a local HTTP directory listing of PS5 .pkg files and build a
Pegasus DL catalog JSON (https://github.com/pegasus-ps5/pegasus-dl).

Usage:
    python3 make_pegasus_catalog.py                      # defaults below
    python3 make_pegasus_catalog.py http://192.168.1.161:8090/ catalog.json

Only stdlib is used. Works with nginx autoindex, Caddy, Python http.server, etc.
"""
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, unquote

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.161:8090/"
OUT = sys.argv[2] if len(sys.argv) > 2 else "catalog.json"
CATALOG_NAME = "My PS5 Library"

GAME_EXT = (".pkg", ".exfat", ".ffpfsc")
TITLE_ID_RE = re.compile(r"(?<![A-Z0-9])(PPSA|CUSA)\d{5}(?:_\d{2})?", re.I)
VERSION_RE = re.compile(r"(?:^|[_\-\s\[(])v?(\d+\.\d{2})(?:[_\-\s\])]|$)", re.I)
CONTENT_ID_RE = re.compile(r"\b[A-Z]{2}\d{4}-(PPSA|CUSA)\d{5}_00-[A-Z0-9]{16}\b", re.I)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            for k, v in attrs:
                if k.lower() == "href" and v:
                    self.links.append(v)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pegasus-catalog/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def head_size(url):
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "pegasus-catalog/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            cl = r.headers.get("Content-Length")
            return int(cl) if cl else None
    except Exception:
        return None


def crawl(url, seen, found):
    """Recursively walk directory listings, collecting .pkg URLs."""
    if url in seen:
        return
    seen.add(url)
    try:
        html = fetch(url)
    except Exception as e:
        print(f"  ! could not read {url}: {e}", file=sys.stderr)
        return

    p = LinkParser()
    p.feed(html)
    for href in p.links:
        full = urljoin(url, href)
        # stay on the same host, don't walk upward
        if urlparse(full).netloc != urlparse(BASE).netloc:
            continue
        if not full.startswith(BASE):
            continue
        path = urlparse(full).path
        if path.lower().endswith(GAME_EXT):
            found.add(full)
        elif path.endswith("/"):
            decoded = unquote(path)
            if "lost+found" in decoded or "/." in decoded:
                continue
            crawl(full, seen, found)


def guess_kind(name):
    n = name.lower()
    if "update" in n or "patch" in n:
        return "Update"
    if "dlc" in n or "addcont" in n:
        return "DLC"
    return "Game"


def clean_title(filename):
    """Turn 'Some_Game-PPSA01234-v1.02.pkg' into 'Some Game'."""
    t = re.sub(r"\.(pkg|exfat|ffpfsc)$", "", filename, flags=re.I)
    t = CONTENT_ID_RE.sub("", t)
    t = TITLE_ID_RE.sub("", t)
    t = VERSION_RE.sub(" ", t)
    t = re.sub(r"[\[\(].*?[\]\)]", " ", t)      # drop [tags] and (notes)
    t = re.sub(r"[_\.]+", " ", t)
    t = re.sub(r"\s*-\s*$", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" -")
    return t or filename


def main():
    print(f"Crawling {BASE} ...")
    seen, found = set(), set()
    crawl(BASE, seen, found)
    print(f"Found {len(found)} package files")

    packages = []
    for url in sorted(found):
        filename = unquote(urlparse(url).path.rsplit("/", 1)[-1])
        m = TITLE_ID_RE.search(filename)
        title_id = m.group(0).upper()[:9] if m else re.sub(r"\W+", "", filename)[:16].upper()
        v = VERSION_RE.search(filename)
        version = v.group(1) if v else "1.00"
        size = head_size(url)

        pkg = {
            "titleId": title_id,
            "title": clean_title(filename),
            "version": version,
            "description": f"{guess_kind(filename)} · {filename.rsplit('.', 1)[-1].upper()} · {filename}",
            "downloadSource": url,
            "downloadLinks": [{"name": "LAN", "url": url}],
        }
        if size:
            pkg["sizeBytes"] = size
        packages.append(pkg)
        print(f"  {title_id:10} v{version:5} {pkg['title']}")

    catalog = {"name": CATALOG_NAME, "packages": packages}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {OUT} with {len(packages)} packages")


if __name__ == "__main__":
    main()
