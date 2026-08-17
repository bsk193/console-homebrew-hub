import json
import os
from update_payloads import update_readme, sanitize_for_filename, sanitize_for_version

JSON_FILE = "payloads.json"
BASE_URL = "https://github.com/bsk193/ps5-payloads-mirror/releases/download/payloads-mirror"
REQUIRED_FIELDS = ["name", "filename", "url", "source", "description", "last_update", "version", "checksum"]

def check_payloads():
    with open(JSON_FILE) as f:
        payloads = json.load(f)

    issues = []
    fixes = []

    # Group by source to detect entries sharing a release
    source_groups = {}
    for i, item in enumerate(payloads):
        src = item.get("source", "")
        if src:
            source_groups.setdefault(src, []).append(i)

    for item in payloads:
        name = item.get("name", "?")

        # Missing required fields
        for field in REQUIRED_FIELDS:
            if not item.get(field):
                issues.append(f"[{name}] missing field: {field}")

        # Entries sharing a source need asset_pattern to avoid ambiguity on update
        src = item.get("source", "")
        if src and len(source_groups.get(src, [])) > 1 and not item.get("asset_pattern"):
            issues.append(f"[{name}] shares source with another entry but has no asset_pattern")

        # Warn about missing category
        if not item.get("category"):
            issues.append(f"[{name}] missing category (will show as Uncategorized in pldmgr)")

        # Auto-fix: normalize filename — name part uses underscores, version part keeps dots
        if item.get("filename") and item.get("version"):
            ext = item["filename"].rsplit(".", 1)[1] if "." in item["filename"] else "elf"
            version_tag = item["version"].split(" FW ")[0] if " FW " in item["version"] else item["version"]
            expected = f"{sanitize_for_filename(name)}_{sanitize_for_version(version_tag)}.{ext}"
            if item["filename"] != expected:
                item["filename"] = expected
                fixes.append(f"[{name}] filename normalized to {expected}")

        # Auto-fix: url should always match BASE_URL/filename
        if item.get("filename"):
            expected_url = f"{BASE_URL}/{item['filename']}"
            if item.get("url") != expected_url:
                item["url"] = expected_url
                fixes.append(f"[{name}] url updated to match normalized filename")

    if fixes:
        with open(JSON_FILE, "w") as f:
            json.dump(payloads, f, indent=2)
        print(f"Auto-fixed {len(fixes)} issue(s):")
        for fix in fixes:
            print(f"  {fix}")
        print()

    if issues:
        print(f"{len(issues)} issue(s) found:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("All entries look good.")

    print()

    # Update README only if content would change
    readme_path = "README.md"
    before = open(readme_path).read() if os.path.exists(readme_path) else ""
    update_readme()
    after = open(readme_path).read() if os.path.exists(readme_path) else ""
    if before != after:
        print("README.md updated.")
    else:
        print("README.md already up to date.")

if __name__ == "__main__":
    check_payloads()
