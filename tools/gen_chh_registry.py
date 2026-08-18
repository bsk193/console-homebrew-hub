#!/usr/bin/env python3
"""
gen_chh_registry.py — generate chh_file_registry.{h,c} and the AppCache manifest
from the CHH frontend files and pldmgrx.elf.

Usage:
    python3 tools/gen_chh_registry.py <chh-repo-root> <pldmgrx-elf-path> <out-dir>

Outputs to <out-dir>:
    chh_file_registry.h   — array type + extern declarations
    chh_file_registry.c   — compressed file data as C arrays
    installer_page.h      — const char* for the installer HTML page
    cache.appcache        — AppCache manifest (also embedded via installer_page.h)
"""

import os
import sys
import zlib
import mimetypes
import textwrap

MIME_MAP = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'application/javascript',
    '.css':  'text/css',
    '.json': 'application/json',
    '.elf':  'application/octet-stream',
    '.bin':  'application/octet-stream',
    '.png':  'image/png',
    '.svg':  'image/svg+xml',
    '.txt':  'text/plain',
    '.appcache': 'text/cache-manifest',
}

def deflate_raw(data):
    """Compress with raw DEFLATE (zlib wbits=-15), compatible with puff()."""
    c = zlib.compressobj(zlib.Z_BEST_COMPRESSION, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()

def c_array_name(url_path):
    """Convert URL path to a valid C identifier."""
    name = url_path.strip('/')
    name = name.replace('/', '_').replace('.', '_').replace('-', '_')
    return 'chh_data_' + name

def mime_for(path):
    ext = os.path.splitext(path)[1].lower()
    return MIME_MAP.get(ext, 'application/octet-stream')

def c_bytes(data, name, col=16):
    """Format bytes as a C uint8_t array."""
    lines = []
    for i in range(0, len(data), col):
        chunk = data[i:i+col]
        lines.append('    ' + ', '.join(f'0x{b:02x}' for b in chunk) + ',')
    return f'static const uint8_t {name}[] = {{\n' + '\n'.join(lines) + '\n};\n'

def c_escape(s):
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n"\n    "')


def collect_frontend_files(repo_root):
    """Return list of (url_path, abs_path) for all files to embed."""
    files = []

    # ── CHH frontend pages ───────────────────────────────────────────────────
    frontend_roots = [
        # (repo_relative_dir,  url_prefix,                      extensions)
        ('ps5',                '/ps5',                          {'.html', '.js', '.css'}),
    ]

    for rel_dir, url_prefix, exts in frontend_roots:
        abs_dir = os.path.join(repo_root, rel_dir)
        for dirpath, dirnames, filenames in os.walk(abs_dir):
            # Skip the exploit core payload ELFs (large, served by the exploit itself)
            dirnames[:] = [d for d in dirnames if d not in ('payloads',)]
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in exts:
                    continue
                abs_path = os.path.join(dirpath, fname)
                rel = os.path.relpath(abs_path, repo_root).replace('\\', '/')
                url = '/' + rel
                files.append((url, abs_path))

    # ── console-nav.js (root level) ─────────────────────────────────────────
    nav = os.path.join(repo_root, 'console-nav.js')
    if os.path.exists(nav):
        files.append(('/console-nav.js', nav))

    return files


def build_appcache(all_urls):
    """Generate the AppCache manifest content."""
    lines = [
        'CACHE MANIFEST',
        '# CHH v1',
        '',
        'CACHE:',
        '/installer/index.html',  # master entry (the page itself)
    ]
    for url in sorted(all_urls):
        lines.append(url)
    lines += [
        '',
        'NETWORK:',
        '*',
        '',
        'FALLBACK:',
    ]
    return '\n'.join(lines) + '\n'


def build_installer_html(appcache_content_escaped):
    """Return the installer trigger page HTML."""
    return textwrap.dedent(f'''\
        <!DOCTYPE html>
        <html manifest="/installer/cache.appcache">
        <head><meta charset="UTF-8"><title>CHH Setup</title></head>
        <body>
        <p id="s">Caching exploit for offline use&hellip;</p>
        <script>
        var ac = window.applicationCache;
        function done() {{
          document.getElementById('s').textContent = 'Done! Shortcut ready for offline use.';
          fetch('/install').catch(function(){{}});
        }}
        if (ac) {{
          ac.addEventListener('cached',   done);
          ac.addEventListener('noupdate', done);
          ac.addEventListener('error',    function() {{
            document.getElementById('s').textContent = 'AppCache error — retrying...';
            setTimeout(function(){{ location.reload(); }}, 2000);
          }});
        }} else {{
          // No AppCache support — just call /install anyway
          done();
        }}
        </script>
        </body>
        </html>
    ''')


def main():
    if len(sys.argv) != 4:
        print(f'Usage: {sys.argv[0]} <repo-root> <pldmgrx-elf> <out-dir>')
        sys.exit(1)

    repo_root, pldmgrx_path, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)

    print(f'[gen] Collecting frontend files from {repo_root}...')
    file_entries = collect_frontend_files(repo_root)

    # Add pldmgrx.elf
    file_entries.append(('/pldmgrx.elf', pldmgrx_path))

    # Generate AppCache manifest
    all_urls = [url for url, _ in file_entries]
    appcache_content = build_appcache(all_urls)

    # Add installer page + appcache as embedded files too
    installer_html = build_installer_html('')
    installer_items = [
        ('/installer/index.html', installer_html.encode()),
        ('/installer/cache.appcache', appcache_content.encode()),
    ]

    print(f'[gen] Compressing {len(file_entries)} files + 2 generated files...')

    # ── Generate chh_file_registry.c ────────────────────────────────────────
    c_lines = [
        '/* AUTO-GENERATED by tools/gen_chh_registry.py — do not edit */',
        '#include <stddef.h>',
        '#include <stdint.h>',
        '#include "chh_file_registry.h"',
        '',
    ]
    registry_entries = []  # (url, array_name, compressed_size, original_size, mime)

    # Disk files
    for url, abs_path in file_entries:
        with open(abs_path, 'rb') as f:
            data = f.read()
        compressed = deflate_raw(data)
        name = c_array_name(url)
        c_lines.append(c_bytes(compressed, name))
        registry_entries.append((url, name, len(compressed), len(data), mime_for(abs_path)))
        print(f'  {url}: {len(data):,} → {len(compressed):,} bytes')

    # Generated in-memory files
    for url, content_bytes in installer_items:
        compressed = deflate_raw(content_bytes)
        name = c_array_name(url)
        c_lines.append(c_bytes(compressed, name))
        registry_entries.append((url, name, len(compressed), len(content_bytes), mime_for(url)))
        print(f'  {url}: {len(content_bytes):,} → {len(compressed):,} bytes (generated)')

    # Registry array
    c_lines.append(f'const ChhFile CHH_FILES[{len(registry_entries)}] = {{')
    for url, name, csz, osz, mime in registry_entries:
        c_lines.append(f'    {{ "{url}", "{mime}", {name}, {csz}UL, {osz}UL }},')
    c_lines.append('};')
    c_lines.append(f'const size_t CHH_FILE_COUNT = {len(registry_entries)};')
    c_lines.append('')

    c_path = os.path.join(out_dir, 'chh_file_registry.c')
    with open(c_path, 'w') as f:
        f.write('\n'.join(c_lines))
    print(f'[gen] Wrote {c_path}')

    # ── Generate chh_file_registry.h ────────────────────────────────────────
    h_lines = [
        '/* AUTO-GENERATED by tools/gen_chh_registry.py — do not edit */',
        '#pragma once',
        '#include <stddef.h>',
        '#include <stdint.h>',
        '',
        'typedef struct {',
        '    const char    *path;',
        '    const char    *content_type;',
        '    const uint8_t *data;          /* raw DEFLATE compressed */',
        '    unsigned long  compressed_size;',
        '    unsigned long  original_size;',
        '} ChhFile;',
        '',
        f'extern const ChhFile CHH_FILES[{len(registry_entries)}];',
        'extern const size_t   CHH_FILE_COUNT;',
        '',
    ]
    h_path = os.path.join(out_dir, 'chh_file_registry.h')
    with open(h_path, 'w') as f:
        f.write('\n'.join(h_lines))
    print(f'[gen] Wrote {h_path}')

    total_orig = sum(e[3] for e in registry_entries)
    total_comp = sum(e[2] for e in registry_entries)
    print(f'[gen] Total: {total_orig:,} bytes → {total_comp:,} bytes compressed '
          f'({100*total_comp//total_orig}% of original)')


if __name__ == '__main__':
    main()
