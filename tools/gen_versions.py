#!/usr/bin/env python3
"""
Generate per-payload version lists (versions/<id>.json) for the
Payload Manager X version picker.

Reads payloads.json, enumerates GitHub releases for each payload,
downloads version ELFs into payloads/, and produces version files
with mirror URLs so every version is downloadable from the release.

Usage:
    python tools/gen_versions.py                     # all payloads
    python tools/gen_versions.py --only "KStuff"     # single payload
    python tools/gen_versions.py --dry-run            # show plan only
    python tools/gen_versions.py --no-experimental    # stable only
"""

import json
import hashlib
import os
import re
import subprocess
import sys
import argparse
import zipfile
import tempfile

# --------------- configuration ---------------
MAX_OLDER_STABLE = 2
INCLUDE_EXPERIMENTAL = True

VERSIONS_DIR = "versions"
PAYLOADS_DIR = "payloads"
PAYLOADS_JSON = "payloads.json"
CACHE_FILE = os.path.join(VERSIONS_DIR, ".checksum_cache.json")
PAGES_BASE = "https://bsk193.github.io/console-homebrew-hub/versions"
MIRROR_REPO = "bsk193/console-homebrew-hub"

# --------------- helpers ---------------

def slugify(name):
    s = name.lower().replace("°", "")
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def get_mirror_base_url():
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{MIRROR_REPO}/releases/latest", "--jq", ".tag_name"],
            capture_output=True, text=True, check=True)
        tag = result.stdout.strip()
        if tag:
            return f"https://github.com/{MIRROR_REPO}/releases/download/{tag}"
    except Exception:
        pass
    return f"https://github.com/{MIRROR_REPO}/releases/latest/download"


def get_github_repo(source_url):
    m = re.search(r'github\.com/([^/]+)/([^/]+)', source_url or '')
    if not m:
        return None, None
    owner, repo = m.group(1), m.group(2).rstrip('/').removesuffix('.git')
    if repo == 'releases':
        return None, None
    return owner, repo


def list_releases(owner, repo):
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{owner}/{repo}/releases?per_page=100"],
            capture_output=True, check=True, encoding='utf-8', errors='replace')
        return [r for r in json.loads(result.stdout) if not r.get('draft')]
    except Exception as e:
        print(f"  ! list_releases {owner}/{repo}: {e}", file=sys.stderr)
        return []


def derive_pattern(source_direct):
    if not source_direct:
        return None
    basename = source_direct.rstrip('/').rsplit('/', 1)[-1]
    if not basename or '.' not in basename:
        return re.escape(basename) if basename else None
    stem, ext = basename.rsplit('.', 1)
    stripped = re.sub(r'[-_]v?\d[\d.\w-]*$', '', stem)
    if stripped and stripped != stem:
        return re.escape(stripped) + r'.*\.(' + re.escape(ext) + r'|zip)'
    return re.escape(stem) + r'.*\.(' + re.escape(ext) + r'|zip)'


def resolve_asset(release, asset_pattern, source_direct):
    assets = release.get('assets', [])
    if not assets:
        return None

    pattern = asset_pattern or derive_pattern(source_direct)
    best, best_score = None, -999

    for a in assets:
        name = a['name']
        nl = name.lower()
        is_std = nl.endswith('.elf') or nl.endswith('.bin')
        is_zip = nl.endswith('.zip')

        if not is_std and not is_zip:
            if not pattern or not re.search(pattern, name, re.I):
                continue
        if pattern and not re.search(pattern, name, re.I):
            if not is_std and not is_zip:
                continue

        score = 0
        if nl.endswith('.elf'):  score += 5
        if nl.endswith('.bin'):  score += 3
        if nl.endswith('.zip'):  score += 1
        if 'ps5' in nl:         score += 10
        if 'ps4' in nl:         score -= 10
        if 'install' in nl:     score -= 5
        score -= len(name) / 100.0

        if score > best_score:
            best_score, best = score, a

    return best


def make_filename(asset_name, tag, extract_name=None):
    base = extract_name or asset_name
    tag_v = tag.lstrip('v').lower()
    if tag_v in base.lower():
        return base
    stem, ext = (base.rsplit('.', 1) + ['elf'])[:2]
    ver = re.sub(r'[^a-zA-Z0-9._-]', '_', tag)
    return f"{stem}_{ver}.{ext}"


def download_and_save(url, dest_path, cache):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        sha = hashlib.sha256()
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        sha.update(data)
        cs = sha.hexdigest()

        with open(dest_path, 'wb') as f:
            f.write(data)

        cache[url] = cs
        return data, cs
    except Exception as e:
        print(f"    ! download {url}: {e}", file=sys.stderr)
        return None, None


def extract_elf_from_zip(zip_data, extract_hint=None):
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        tmp.write(zip_data)
        tmp_path = tmp.name

    try:
        with zipfile.ZipFile(tmp_path, 'r') as z:
            elf_files = [n for n in z.namelist() if n.lower().endswith('.elf')]
            if not elf_files:
                return None, None

            if extract_hint:
                match = [n for n in elf_files if n.lower() == extract_hint.lower()]
                target = match[0] if match else elf_files[0]
            else:
                target = elf_files[0]

            data = z.read(target)
            return target, data
    except Exception as e:
        print(f"    ! zip extract: {e}", file=sys.stderr)
        return None, None
    finally:
        os.unlink(tmp_path)


def load_cache():
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache):
    os.makedirs(VERSIONS_DIR, exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


# --------------- main ---------------

def main():
    ap = argparse.ArgumentParser(description="Generate per-payload version lists")
    ap.add_argument('--only', help='Process only this payload name')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-experimental', action='store_true')
    args = ap.parse_args()

    include_exp = INCLUDE_EXPERIMENTAL and not args.no_experimental

    with open(PAYLOADS_JSON) as f:
        payloads = json.load(f)

    cache = load_cache()
    os.makedirs(VERSIONS_DIR, exist_ok=True)
    os.makedirs(PAYLOADS_DIR, exist_ok=True)

    mirror_base = get_mirror_base_url()
    print(f"[gen_versions] Mirror base: {mirror_base}")

    updated_entries = {}

    for entry in payloads:
        name = entry.get('name', '')
        source = entry.get('source', '')

        if args.only and name != args.only:
            continue
        if 'github.com' not in source:
            continue

        owner, repo = get_github_repo(source)
        if not owner:
            continue

        print(f"\n--- {name} ({owner}/{repo}) ---")
        releases = list_releases(owner, repo)
        if not releases:
            print("  0 releases, skipping")
            continue

        releases.sort(key=lambda r: r.get('published_at', ''), reverse=True)

        latest_idx = next(
            (i for i, r in enumerate(releases) if not r.get('prerelease')),
            None)
        if latest_idx is None:
            print("  no stable release found, skipping")
            continue

        latest_tag = releases[latest_idx]['tag_name']
        print(f"  latest stable: {latest_tag}")

        picks = []

        # Latest stable
        picks.append((releases[latest_idx], 'stable'))

        # ALL pre-releases (newer and older than latest)
        if include_exp:
            for i, r in enumerate(releases):
                if i != latest_idx and r.get('prerelease'):
                    picks.append((r, 'experimental'))

        # Two stable releases before latest
        n = 0
        for i in range(latest_idx + 1, len(releases)):
            if not releases[i].get('prerelease') and n < MAX_OLDER_STABLE:
                picks.append((releases[i], 'stable'))
                n += 1

        slug = slugify(name)
        ap_val = entry.get('asset_pattern')
        sd_val = entry.get('source_direct')
        ef_val = entry.get('extract_file')
        ver_entries = []

        for rel, channel in picks:
            tag = rel['tag_name']
            date = rel.get('published_at', '')[:10]
            asset = resolve_asset(rel, ap_val, sd_val)
            if not asset:
                print(f"  {tag}: no matching asset")
                continue

            dl_url = asset['browser_download_url']
            asset_name = asset['name']
            is_zip = asset_name.lower().endswith('.zip')

            if is_zip:
                elf_name_hint = ef_val or None
                fname = make_filename(asset_name.rsplit('.', 1)[0] + '.elf', tag)
            else:
                fname = make_filename(asset_name, tag)

            if args.dry_run:
                print(f"  {tag} ({channel}): {asset_name} -> {fname}")
                ver_entries.append(True)
                continue

            print(f"  {tag} ({channel}): {asset_name} -> {fname}")
            dest_path = os.path.join(PAYLOADS_DIR, fname)

            # Check if already downloaded
            if os.path.exists(dest_path) and dl_url in cache:
                cs = cache[dl_url]
                print(f"    (cached)")
            else:
                raw_data, cs = download_and_save(dl_url, dest_path, cache)
                if not raw_data:
                    continue

                if is_zip:
                    extract_name, elf_data = extract_elf_from_zip(raw_data, elf_name_hint)
                    if not elf_data:
                        print(f"    ! no .elf found in zip")
                        os.remove(dest_path)
                        continue
                    with open(dest_path, 'wb') as f:
                        f.write(elf_data)
                    cs = hashlib.sha256(elf_data).hexdigest()
                    cache[dl_url] = cs
                    print(f"    extracted {extract_name} from zip")

            mirror_url = f"{mirror_base}/{fname}"

            ve = {
                "name": name,
                "filename": fname,
                "version": tag,
                "url": mirror_url,
                "checksum": cs,
                "channel": channel,
                "category": entry.get('category', 'Utilities'),
                "last_update": date
            }
            if entry.get('description'):
                ve['description'] = entry['description']
            if entry.get('min_fw'):
                ve['min_fw'] = entry['min_fw']
            if entry.get('max_fw'):
                ve['max_fw'] = entry['max_fw']

            ver_entries.append(ve)

        if not ver_entries:
            continue

        if args.dry_run:
            print(f"  -> versions/{slug}.json ({len(ver_entries)} versions)")
        else:
            out = os.path.join(VERSIONS_DIR, f"{slug}.json")
            with open(out, 'w') as f:
                json.dump(ver_entries, f, indent=2)
            print(f"  wrote {out} ({len(ver_entries)} versions)")

        updated_entries[name] = slug

    # --- add versions_url to payloads.json ---
    if not args.dry_run and updated_entries:
        changed = False
        for entry in payloads:
            n = entry.get('name', '')
            if n in updated_entries:
                vurl = f"{PAGES_BASE}/{updated_entries[n]}.json"
                if entry.get('versions_url') != vurl:
                    entry['versions_url'] = vurl
                    changed = True
        if changed:
            with open(PAYLOADS_JSON, 'w') as f:
                json.dump(payloads, f, indent=2)
            print(f"\nUpdated {PAYLOADS_JSON}: {len(updated_entries)} entries got versions_url")

    save_cache(cache)
    print("\nDone.")


if __name__ == '__main__':
    main()
