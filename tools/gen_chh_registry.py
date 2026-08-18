#!/usr/bin/env python3
"""
gen_chh_registry.py — generate CHH file registry using .incbin assembly.

Instead of C byte-array literals (slow to compile), each compressed blob is
written as a raw binary file and included via assembly .incbin directives.
The C file only contains the tiny metadata array.

Usage:
    python3 tools/gen_chh_registry.py <chh-repo-root> <pldmgrx-elf-path> <out-dir>

Outputs to <out-dir>:
    chh_blob_NNN.deflate    — raw DEFLATE-compressed blobs
    chh_data.S              — assembly that .incbin's each blob into .rodata
    chh_file_registry.c     — ChhFile metadata array (no bulk data)
    chh_file_registry.h     — ChhFile struct + extern declarations
"""

import os
import sys
import zlib

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
    c = zlib.compressobj(zlib.Z_BEST_COMPRESSION, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()

def mime_for(path):
    ext = os.path.splitext(path)[1].lower()
    return MIME_MAP.get(ext, 'application/octet-stream')

def blob_sym(index):
    return f'_chh_blob_{index:03d}'

def collect_frontend_files(repo_root):
    files = []

    abs_dir = os.path.join(repo_root, 'ps5')
    for dirpath, dirnames, filenames in os.walk(abs_dir):
        dirnames[:] = [d for d in dirnames if d not in ('payloads',)]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in {'.html', '.js', '.css'}:
                continue
            abs_path = os.path.join(dirpath, fname)
            rel = os.path.relpath(abs_path, repo_root).replace('\\', '/')
            files.append(('/' + rel, abs_path))

    nav = os.path.join(repo_root, 'console-nav.js')
    if os.path.exists(nav):
        files.append(('/console-nav.js', nav))

    return files

def build_appcache(all_urls):
    lines = [
        'CACHE MANIFEST',
        '# CHH v1',
        '',
        'CACHE:',
        '/installer/index.html',
    ]
    for url in sorted(all_urls):
        lines.append(url)
    lines += ['', 'NETWORK:', '*', '', 'FALLBACK:']
    return '\n'.join(lines) + '\n'

def build_installer_html():
    return (
        '<!DOCTYPE html>\n'
        '<html manifest="/installer/cache.appcache">\n'
        '<head><meta charset="UTF-8"><title>CHH Setup</title></head>\n'
        '<body>\n'
        '<p id="s">Caching exploit for offline use&hellip;</p>\n'
        '<script>\n'
        'var ac = window.applicationCache;\n'
        'function done() {\n'
        '  document.getElementById("s").textContent = "Done! Shortcut ready.";\n'
        '  fetch("/install").catch(function(){});\n'
        '}\n'
        'if (ac) {\n'
        '  ac.addEventListener("cached",   done);\n'
        '  ac.addEventListener("noupdate", done);\n'
        '  ac.addEventListener("error", function() {\n'
        '    document.getElementById("s").textContent = "AppCache error — retrying...";\n'
        '    setTimeout(function(){ location.reload(); }, 2000);\n'
        '  });\n'
        '} else { done(); }\n'
        '</script>\n'
        '</body>\n'
        '</html>\n'
    )

def main():
    if len(sys.argv) != 4:
        print(f'Usage: {sys.argv[0]} <repo-root> <pldmgrx-elf> <out-dir>')
        sys.exit(1)

    repo_root, pldmgrx_path, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)

    print(f'[gen] Collecting frontend files from {repo_root}...')
    file_entries = collect_frontend_files(repo_root)
    file_entries.append(('/pldmgrx.elf', pldmgrx_path))

    all_urls = [url for url, _ in file_entries]
    appcache_content = build_appcache(all_urls)
    installer_html = build_installer_html()

    generated = [
        ('/installer/index.html',    installer_html.encode()),
        ('/installer/cache.appcache', appcache_content.encode()),
    ]

    # Build full list: (url, mime, compressed_bytes, original_size)
    entries = []
    total_orig = total_comp = 0

    for url, abs_path in file_entries:
        with open(abs_path, 'rb') as f:
            data = f.read()
        comp = deflate_raw(data)
        entries.append((url, mime_for(abs_path), comp, len(data)))
        total_orig += len(data)
        total_comp += len(comp)
        print(f'  {url}: {len(data):,} -> {len(comp):,}')

    for url, content_bytes in generated:
        comp = deflate_raw(content_bytes)
        entries.append((url, mime_for(url), comp, len(content_bytes)))
        total_orig += len(content_bytes)
        total_comp += len(comp)
        print(f'  {url}: {len(content_bytes):,} -> {len(comp):,} (generated)')

    print(f'[gen] Total: {total_orig:,} -> {total_comp:,} bytes '
          f'({100*total_comp//total_orig}% of original)')

    # ── Write raw blob files ─────────────────────────────────────────────────
    for i, (url, mime, comp, orig) in enumerate(entries):
        blob_path = os.path.join(out_dir, f'chh_blob_{i:03d}.deflate')
        with open(blob_path, 'wb') as f:
            f.write(comp)

    # ── Write chh_data.S (assembly with .incbin) ─────────────────────────────
    asm_lines = [
        '/* AUTO-GENERATED by tools/gen_chh_registry.py — do not edit */',
        '\t.section .rodata,"a",@progbits',
        '',
    ]
    for i, (url, mime, comp, orig) in enumerate(entries):
        sym = blob_sym(i)
        fname = f'chh_blob_{i:03d}.deflate'
        asm_lines += [
            f'\t.global {sym}',
            f'\t.type {sym}, @object',
            f'{sym}:',
            f'\t.incbin "{fname}"',
            f'{sym}_end:',
            f'\t.size {sym}, {sym}_end - {sym}',
            '',
        ]
    s_path = os.path.join(out_dir, 'chh_data.S')
    with open(s_path, 'w') as f:
        f.write('\n'.join(asm_lines))
    print(f'[gen] Wrote {s_path}')

    # ── Write chh_file_registry.c (metadata only) ────────────────────────────
    c_lines = [
        '/* AUTO-GENERATED by tools/gen_chh_registry.py — do not edit */',
        '#include <stddef.h>',
        '#include <stdint.h>',
        '#include "chh_file_registry.h"',
        '',
    ]
    for i, (url, mime, comp, orig) in enumerate(entries):
        c_lines.append(f'extern const uint8_t {blob_sym(i)}[];')
    c_lines.append('')
    c_lines.append(f'const ChhFile CHH_FILES[{len(entries)}] = {{')
    for i, (url, mime, comp, orig) in enumerate(entries):
        c_lines.append(
            f'    {{ "{url}", "{mime}", {blob_sym(i)}, {len(comp)}UL, {orig}UL }},'
        )
    c_lines.append('};')
    c_lines.append(f'const size_t CHH_FILE_COUNT = {len(entries)};')
    c_lines.append('')
    c_path = os.path.join(out_dir, 'chh_file_registry.c')
    with open(c_path, 'w') as f:
        f.write('\n'.join(c_lines))
    print(f'[gen] Wrote {c_path}')

    # ── Write chh_file_registry.h ─────────────────────────────────────────────
    h_lines = [
        '/* AUTO-GENERATED by tools/gen_chh_registry.py — do not edit */',
        '#pragma once',
        '#include <stddef.h>',
        '#include <stdint.h>',
        '',
        'typedef struct {',
        '    const char    *path;',
        '    const char    *content_type;',
        '    const uint8_t *data;',
        '    unsigned long  compressed_size;',
        '    unsigned long  original_size;',
        '} ChhFile;',
        '',
        f'extern const ChhFile CHH_FILES[{len(entries)}];',
        'extern const size_t   CHH_FILE_COUNT;',
        '',
    ]
    h_path = os.path.join(out_dir, 'chh_file_registry.h')
    with open(h_path, 'w') as f:
        f.write('\n'.join(h_lines))
    print(f'[gen] Wrote {h_path}')


if __name__ == '__main__':
    main()
