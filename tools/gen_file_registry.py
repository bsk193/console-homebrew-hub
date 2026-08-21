#!/usr/bin/env python3
"""Generate a C file registry + per-exploit AppCache manifests from a staged dist directory.

Scans <dist_dir> recursively and produces:
  - <header_out>  : file_registry.h  (FileEntry struct + extern table)
  - <source_out>  : file_registry.c  (byte arrays + lookup function)
  - <dist_dir>/cache-{exploit}.appcache  (per-exploit AppCache manifests)
  - <dist_dir>/ps5/chh-{exploit}.html    (per-exploit installer pages)

Each exploit (umtx, ipv6, slopkit) gets its own manifest that caches only
that exploit's core files, keeping AppCache under ~20 MB to avoid OOM on PS5.

Based on ps5-webkit-autoloader's gen_file_registry.py by PLK,
adapted for Console Homebrew Hub with per-exploit offline caching.

Usage: gen_file_registry.py <dist_dir> <header_out> <source_out>
"""

import hashlib
import os
import posixpath
import re
import sys
import zlib

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".appcache": "text/cache-manifest",
    ".txt": "text/plain",
    ".elf": "application/octet-stream",
    ".bin": "application/octet-stream",
}

EXCLUDE_PATTERNS = [
    "/.git/",
    "/.github/",
    "/chh-src/",
    "/tools/",
]

EXPLOIT_NAMES = ["umtx", "ipv6", "slopkit"]


def detect_content_type(path):
    ext = os.path.splitext(path)[1].lower()
    return CONTENT_TYPES.get(ext, "application/octet-stream")


def include_in_registry(path):
    for pat in EXCLUDE_PATTERNS:
        if pat in path or path.endswith(pat.rstrip("/")):
            return False
    if path.endswith(".sha256"):
        return False
    if path.endswith(".appcache"):
        return False
    if "/slopkit/readme.png" in path.lower():
        return False
    # Keep elfldr from exploit cores (needed for exploit to boot).
    # Exclude other ELF payloads (ftpsrv, gdbsrv, kstuff — unnecessary bulk).
    if "/exploits/" in path and path.endswith(".elf"):
        return "elfldr" in os.path.basename(path).lower()
    return True


def compress_entry(data):
    if len(data) < 64:
        return data, False
    co = zlib.compressobj(level=9, wbits=-15)
    comp = co.compress(data) + co.flush()
    if len(comp) >= len(data):
        return data, False
    return comp, True


def emit_c_array(out, name, data):
    out.write(f"static const unsigned char {name}[] = {{\n")
    for i in range(0, len(data), 12):
        chunk = ", ".join(f"0x{b:02x}" for b in data[i : i + 12])
        out.write(f"    {chunk},\n")
    out.write("};\n")


def strip_manifest_attr(data, path):
    """Strip manifest= from exploit core HTML (prevent nested AppCache)."""
    if not path.endswith(".html"):
        return data
    if b"/core/" not in path.encode() and b"\\core\\" not in path.encode():
        return data
    text = data.decode("utf-8", errors="replace")
    patched = re.sub(
        r'(<html\b[^>]*?)\s+manifest\s*=\s*["\'][^"\']*["\']',
        r'\1',
        text,
        count=1,
    )
    return patched.encode("utf-8")


def exploit_for_path(path):
    """Return exploit name if path is under an exploit directory, else None."""
    for name in EXPLOIT_NAMES:
        if f"/ps5/exploits/{name}/" in path:
            return name
    return None


# Slopkit iframe URL — must match EXPLOIT_BASE + EXPLOIT_PARAMS in the
# slopkit wrapper (ps5/exploits/slopkit/index.html). AppCache needs the
# exact URL to serve this page offline.
SLOPKIT_IFRAME_URL = (
    "/ps5/exploits/slopkit/core/slopkit/poops.html"
    "?go=1&auto=1&production=1&trigger=netcontrol&attempts=8"
    "&only=ps0_preflight,ps1_prepare,ps3_stage0,ps4_validate"
    ",ps5_stage1,ps6_stage2,ps8_stage3,ps9_stage4,ps10_stage5"
    "&log=debug&v=final"
)

# UMTX/IPV6 iframe URLs — autoload=pldmgrx.elf for offline shortcut mode.
UMTX_IFRAME_URL = "/ps5/exploits/umtx/core/document/en/ps5/index.html?autoload=pldmgrx.elf"
IPV6_IFRAME_URL = "/ps5/exploits/ipv6/core/document/en/ps5/index.html?autoload=pldmgrx.elf"

EXPLOIT_IFRAME_URLS = {
    "slopkit": SLOPKIT_IFRAME_URL,
    "umtx": UMTX_IFRAME_URL,
    "ipv6": IPV6_IFRAME_URL,
}

CACHEBUST_RE = re.compile(r'([A-Za-z0-9_./-]+\.(?:js|css|html|png|jpg|gif))\?v=[A-Za-z0-9]+')


def collect_cachebust_urls(files):
    """Scan HTML/JS for cache-busting query string imports (slopkit's ?v=
    patterns). AppCache matches URLs exactly, so these variants must be
    listed in the manifest or offline loads will fail."""
    urls = set()
    for path, full in files:
        if not (path.endswith(".html") or path.endswith(".js")):
            continue
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                data = f.read()
        except OSError:
            continue
        base = posixpath.dirname(path)
        for match in CACHEBUST_RE.finditer(data):
            ref = match.group(1)
            full_match = match.group(0)
            query = full_match[len(ref):]
            resolved = posixpath.normpath(posixpath.join(base, ref))
            if resolved.startswith("/") and "/slopkit/" in resolved:
                urls.add(resolved + query)
    # Also add ?v=final to all slopkit offset files (loaded dynamically)
    for path, _ in files:
        if "/slopkit/" in path and "/offsets/" in path and path.endswith(".js"):
            urls.add(path + "?v=final")
    return sorted(urls)


COMPLETE_PATH = "/__complete__"

# Redirect page replaces chh.html — detects firmware, redirects to per-exploit installer.
CHH_REDIRECT_HTML = r'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CHH Installer</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#06060f;display:flex;align-items:center;justify-content:center;min-height:100vh;font:500 14px system-ui;color:#dde4f2;flex-direction:column;gap:16px;padding:20px}
.card{background:#0c0c1a;border:1px solid #1c1c30;border-radius:16px;padding:24px;width:100%;max-width:340px;text-align:center;display:flex;flex-direction:column;align-items:center;gap:14px}
.logo{width:56px;height:56px;border-radius:14px;background:linear-gradient(135deg,#4f87ff,#1957c8);display:flex;align-items:center;justify-content:center;font:800 14px/1 system-ui;color:#fff}
h1{font:700 18px/1.2 system-ui;color:#fff}
.msg{font:400 13px/1.5 system-ui;color:#50608a}
</style>
</head>
<body>
<div class="card">
  <div class="logo">CHH</div>
  <h1>Console Homebrew Hub</h1>
  <div class="msg" id="msg">Detecting firmware&hellip;</div>
</div>
<script>
(function(){
  var msg=document.getElementById('msg');
  var IPV6_FWS={'3.00':1,'3.10':1,'3.20':1,'3.21':1,'4.00':1,'4.02':1,'4.03':1,'4.50':1,'4.51':1};
  function pick(fw){
    if(!fw)return null;
    if(IPV6_FWS[fw])return'ipv6';
    var v=parseFloat(fw);
    if(isNaN(v))return null;
    if(v<=5.50)return'umtx';
    if(v<9.00)return null;
    if(v<=12.00)return'slopkit';
    return null;
  }
  var xhr=new XMLHttpRequest();
  xhr.open('GET','/version',true);
  xhr.timeout=3000;
  xhr.onload=function(){
    if(xhr.status!==200){window.location.replace('/ps5/index.html');return;}
    var ua=navigator.userAgent||'';
    var m=ua.match(/PlayStation 5[\/\s]+([\d.]+)/);
    var fw=m?m[1]:null;
    var exploit=pick(fw);
    if(exploit){
      msg.textContent='Caching '+exploit.toUpperCase()+' exploit…';
      window.location.replace('/ps5/chh-'+exploit+'.html');
    }else{
      msg.textContent='No offline exploit for FW '+(fw||'unknown');
      setTimeout(function(){window.location.replace('/ps5/index.html');},3000);
    }
  };
  xhr.onerror=function(){window.location.replace('/ps5/index.html');};
  xhr.ontimeout=function(){window.location.replace('/ps5/index.html');};
  xhr.send();
})();
</script>
</body>
</html>
'''


def generate_exploit_files(dist_dir, files):
    """Generate per-exploit installer pages from chh.html and replace it with redirect."""
    chh_data = None
    for path, full in files:
        if path == "/ps5/chh.html":
            with open(full, "rb") as f:
                chh_data = f.read()
            break

    if chh_data is None:
        print("Warning: /ps5/chh.html not found, skipping per-exploit generation")
        return files

    new_files = []
    for exploit in EXPLOIT_NAMES:
        text = chh_data.decode("utf-8", errors="replace")
        manifest_url = "/cache-" + exploit + ".appcache"
        text = re.sub(
            r"(<html)\b", r'\1 manifest="' + manifest_url + '"', text, count=1
        )
        text = text.replace(
            "completed = true;",
            "completed = true;"
            "try{localStorage.setItem('chh_exploit','" + exploit + "')}catch(x){}",
            1,
        )
        page_name = "chh-" + exploit + ".html"
        page_full = os.path.join(dist_dir, "ps5", page_name)
        with open(page_full, "w", encoding="utf-8") as f:
            f.write(text)
        new_files.append(("/ps5/" + page_name, page_full))

    # Overwrite chh.html with firmware-detection redirect
    chh_full = os.path.join(dist_dir, "ps5", "chh.html")
    with open(chh_full, "w", encoding="utf-8") as f:
        f.write(CHH_REDIRECT_HTML)

    return files + new_files


def build_manifest(files, content_hash, cachebust_urls, exploit):
    """Build a per-exploit AppCache manifest.

    Only caches the specified exploit's core files plus all shared assets.
    __complete__ is listed LAST in the CACHE section for integrity validation.
    """
    lines = [
        "CACHE MANIFEST",
        "# CHH " + content_hash + " " + exploit,
        "",
        "CACHE:",
    ]
    for path, _ in files:
        if path.endswith(".appcache") or path == COMPLETE_PATH:
            continue
        file_exploit = exploit_for_path(path)
        if file_exploit and file_exploit != exploit:
            continue
        lines.append(path)

    # Exploit iframe URL with query string
    lines.append(EXPLOIT_IFRAME_URLS[exploit])

    # Cache-busted script imports (filtered by exploit)
    for url in cachebust_urls:
        url_exploit = exploit_for_path(url)
        if url_exploit and url_exploit != exploit:
            continue
        lines.append(url)

    # __complete__ marker — LAST entry
    lines.append(COMPLETE_PATH)

    lines += [
        "",
        "NETWORK:",
        "/install",
        "/version",
        "*",
        "",
        "FALLBACK:",
        "/ /ps5/index.html",
        "",
    ]
    return "\n".join(lines)


def main():
    if len(sys.argv) != 4:
        print("Usage: gen_file_registry.py <dist_dir> <header_out> <source_out>")
        sys.exit(1)

    dist_dir, header_out, source_out = sys.argv[1:4]

    if not os.path.isdir(dist_dir):
        print(f"Error: {dist_dir} not found or not a directory.")
        sys.exit(1)

    files = []
    for root, dirs, names in os.walk(dist_dir):
        dirs.sort()
        for name in sorted(names):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, dist_dir).replace(os.sep, "/")
            path = f"/{rel}"
            if not include_in_registry(path):
                continue
            files.append((path, full))
    files.sort(key=lambda f: f[0])

    # Generate per-exploit installer pages and redirect
    files = generate_exploit_files(dist_dir, files)
    files.sort(key=lambda f: f[0])

    # Content hash for manifest versioning (after per-exploit files exist)
    h = hashlib.md5()
    for path, full in files:
        with open(full, "rb") as f:
            h.update(f.read())
    content_hash = h.hexdigest()[:8]

    # Create __complete__ marker
    complete_full = os.path.join(dist_dir, "__complete__")
    with open(complete_full, "w", encoding="utf-8") as f:
        f.write(content_hash)
    files.append((COMPLETE_PATH, complete_full))
    files.sort(key=lambda f: f[0])

    # Collect cache-bust URLs before writing manifests
    cachebust_urls = collect_cachebust_urls(files)

    # Write per-exploit manifests
    for exploit in EXPLOIT_NAMES:
        manifest_content = build_manifest(files, content_hash, cachebust_urls, exploit)
        manifest_name = "cache-" + exploit + ".appcache"
        manifest_full = os.path.join(dist_dir, manifest_name)
        with open(manifest_full, "w") as f:
            f.write(manifest_content)
        files.append(("/" + manifest_name, manifest_full))
    files.sort(key=lambda f: f[0])

    # Header
    with open(header_out, "w") as out:
        out.write("/* Auto-generated by tools/gen_file_registry.py — do not edit. */\n\n")
        out.write("#ifndef FILE_REGISTRY_H\n")
        out.write("#define FILE_REGISTRY_H\n\n")
        out.write("typedef struct {\n")
        out.write("    const char *path;\n")
        out.write("    const unsigned char *data;\n")
        out.write("    unsigned int size;\n")
        out.write("    unsigned int orig_size;\n")
        out.write("    unsigned char compressed;\n")
        out.write("    const char *content_type;\n")
        out.write("} FileEntry;\n\n")
        out.write("extern const FileEntry file_registry[];\n")
        out.write("extern const unsigned int file_registry_count;\n\n")
        out.write("const FileEntry *file_registry_find(const char *path);\n\n")
        out.write("#endif /* FILE_REGISTRY_H */\n")

    # Source
    with open(source_out, "w") as out:
        out.write("/* Auto-generated by tools/gen_file_registry.py — do not edit. */\n\n")
        out.write('#include <string.h>\n')
        out.write('#include "file_registry.h"\n\n')

        entries = []
        total_raw = 0
        total_stored = 0
        for i, (path, full) in enumerate(files):
            with open(full, "rb") as f:
                data = f.read()
            data = strip_manifest_attr(data, path)
            stored, compressed = compress_entry(data)
            emit_c_array(out, f"file_{i}", stored)
            out.write("\n")
            entries.append((path, compressed, len(data), len(stored)))
            total_raw += len(data)
            total_stored += len(stored)

        out.write("const FileEntry file_registry[] = {\n")
        for i, (path, full) in enumerate(files):
            content_type = detect_content_type(path)
            _, compressed, orig_size, stored_size = entries[i]
            out.write(
                f'    {{ "{path}", file_{i}, {stored_size}, {orig_size}, '
                f'{1 if compressed else 0}, "{content_type}" }},\n'
            )
        out.write("};\n\n")
        out.write("const unsigned int file_registry_count =\n")
        out.write("    sizeof(file_registry) / sizeof(file_registry[0]);\n\n")
        out.write("const FileEntry *file_registry_find(const char *path) {\n")
        out.write("    if (!path) return NULL;\n")
        out.write("    for (unsigned int i = 0; i < file_registry_count; i++) {\n")
        out.write('        if (strcmp(file_registry[i].path, path) == 0)\n')
        out.write("            return &file_registry[i];\n")
        out.write("    }\n")
        out.write("    return NULL;\n")
        out.write("}\n")

    print(f"Generated {header_out} and {source_out}")
    print(f"  {len(files)} files, {total_raw:,} bytes raw, {total_stored:,} bytes stored "
          f"({100 * total_stored / max(total_raw, 1):.0f}%)")
    for exploit in EXPLOIT_NAMES:
        count = sum(1 for p, _ in files
                    if not p.endswith(".appcache") and p != COMPLETE_PATH
                    and (exploit_for_path(p) in (exploit, None)))
        print(f"  cache-{exploit}.appcache: {count} entries")


if __name__ == "__main__":
    main()
