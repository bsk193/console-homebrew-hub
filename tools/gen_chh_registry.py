#!/usr/bin/env python3
"""
gen_chh_registry.py — generate CHH file registry using .incbin assembly.

Small files (hub/wrapper HTML pages, console-nav.js) are embedded in the ELF.
Large files (exploit cores, pldmgrx.elf) are proxied from the PC at runtime.

The AppCache manifest is generated DYNAMICALLY by the ELF at runtime based on
which exploit was just used (passed as ?exploit=X query param).  This ensures
AppCache only downloads the ~25 files for ONE exploit rather than all 105, so
the background download completes quickly before the user can retry.

Usage:
    python3 tools/gen_chh_registry.py <chh-repo-root> <pldmgrx-elf-path> <out-dir>

Outputs to <out-dir>:
    chh_blob_NNN.deflate    — raw DEFLATE-compressed blobs (embedded files only)
    chh_data.S              — assembly .incbin for each blob
    chh_file_registry.c     — ChhFile metadata array
    chh_file_registry.h     — ChhFile struct + extern declarations
    chh_proxy_paths.h       — per-exploit proxy path lists for dynamic manifest
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

def should_embed(url):
    """Return True for small files to embed in the ELF binary."""
    if url == '/pldmgrx.elf':
        return False
    if url.startswith('/ps5/exploits/') and '/core/' in url:
        return False
    return True

def exploit_for(url):
    """Return exploit name (slopkit/umtx/ipv6) for a core file URL, else None."""
    for name in ('slopkit', 'umtx', 'ipv6'):
        if url.startswith(f'/ps5/exploits/{name}/'):
            return name
    return None

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

def c_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

def main():
    if len(sys.argv) != 4:
        print(f'Usage: {sys.argv[0]} <repo-root> <pldmgrx-elf> <out-dir>')
        sys.exit(1)

    repo_root, pldmgrx_path, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)

    print(f'[gen] Collecting frontend files from {repo_root}...')
    all_file_entries = collect_frontend_files(repo_root)
    all_file_entries.append(('/pldmgrx.elf', pldmgrx_path))

    # Split into embedded (small) and proxy (large) entries
    embed_file_entries = [(u, p) for u, p in all_file_entries if should_embed(u)]
    proxy_file_entries = [(u, p) for u, p in all_file_entries if not should_embed(u)]

    print(f'[gen] Embedding {len(embed_file_entries)} small files, '
          f'proxying {len(proxy_file_entries)} large files from PC')

    # Compress embedded files
    entries = []  # (url, mime, compressed_bytes, original_size)
    total_orig = total_comp = 0

    for url, abs_path in embed_file_entries:
        with open(abs_path, 'rb') as f:
            data = f.read()
        comp = deflate_raw(data)
        entries.append((url, mime_for(abs_path), comp, len(data)))
        total_orig += len(data)
        total_comp += len(comp)
        print(f'  [embed] {url}: {len(data):,} -> {len(comp):,}')

    for url, abs_path in proxy_file_entries:
        print(f'  [proxy] {url}: {os.path.getsize(abs_path):,} bytes (PC:6969)')

    # Add generated installer HTML (embedded; manifest is dynamic, not embedded)
    installer_html = build_installer_html().encode()
    comp = deflate_raw(installer_html)
    entries.append(('/installer/index.html', 'text/html; charset=utf-8', comp, len(installer_html)))
    total_orig += len(installer_html)
    total_comp += len(comp)
    print(f'  [embed] /installer/index.html: {len(installer_html):,} -> {len(comp):,} (generated)')

    print(f'[gen] Embedded total: {total_orig:,} -> {total_comp:,} bytes, '
          f'{len(entries)} files')

    # ── Write raw blob files ─────────────────────────────────────────────────
    for i, (url, mime, comp, orig) in enumerate(entries):
        blob_path = os.path.join(out_dir, f'chh_blob_{i:03d}.deflate')
        with open(blob_path, 'wb') as f:
            f.write(comp)

    # ── Write chh_data.S ─────────────────────────────────────────────────────
    asm_lines = [
        '/* AUTO-GENERATED by tools/gen_chh_registry.py — do not edit */',
        '\t.section .rodata,"a",@progbits',
        '',
    ]
    for i, (url, mime, comp, orig) in enumerate(entries):
        sym = blob_sym(i)
        fname = f'src/chh_blob_{i:03d}.deflate'
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

    # ── Write chh_file_registry.c ─────────────────────────────────────────────
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
            f'    {{ {c_str(url)}, {c_str(mime)}, {blob_sym(i)}, {len(comp)}UL, {orig}UL }},'
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

    # ── Write chh_proxy_paths.h (per-exploit path lists for dynamic manifest) ──
    # Group proxy files by exploit name; /pldmgrx.elf appended to each list
    by_exploit = {'slopkit': [], 'umtx': [], 'ipv6': []}
    for url, _ in proxy_file_entries:
        ex = exploit_for(url)
        if ex and ex in by_exploit:
            by_exploit[ex].append(url)

    px_lines = [
        '/* AUTO-GENERATED by tools/gen_chh_registry.py — do not edit */',
        '#pragma once',
        '',
    ]
    for ex, paths in by_exploit.items():
        sym = f'CHH_PROXY_{ex.upper()}'
        px_lines.append(f'static const char * const {sym}[] = {{')
        for p in sorted(paths):
            px_lines.append(f'    {c_str(p)},')
        px_lines.append('    "/pldmgrx.elf",')
        px_lines.append('    NULL')
        px_lines.append('};')
        px_lines.append(f'#define {sym}_COUNT {len(paths) + 1}')
        px_lines.append('')

    px_path = os.path.join(out_dir, 'chh_proxy_paths.h')
    with open(px_path, 'w') as f:
        f.write('\n'.join(px_lines))
    print(f'[gen] Wrote {px_path}')
    for ex, paths in by_exploit.items():
        print(f'  {ex}: {len(paths)} core files + pldmgrx.elf')


if __name__ == '__main__':
    main()
