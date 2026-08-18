#!/usr/bin/env python3
"""Console Homebrew Hub — Local Host
Run from the CHH repo root. Downloads missing ELF assets and serves on port 6969.
"""
import http.server, os, socket, urllib.request

PORT = 6969
CHH_RELEASE = "https://github.com/bsk193/console-homebrew-hub/releases/download/chh-latest"
REQUIRED_FILES = [
    "chh-installer.elf",
    "chh-local-installer.elf",
    "pldmgrx.elf",
]


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def download_if_missing(filename):
    if not os.path.exists(filename):
        url = f"{CHH_RELEASE}/{filename}"
        print(f"  Downloading {filename}...")
        try:
            urllib.request.urlretrieve(url, filename)
            print(f"    OK ({os.path.getsize(filename):,} bytes)")
        except Exception as e:
            print(f"    WARN: could not download {filename}: {e}")
            print(f"    Get manually: {url}")


class _SilentHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    print("Console Homebrew Hub — Local Host")
    print("Checking required assets...")
    for f in REQUIRED_FILES:
        download_if_missing(f)

    ip = get_local_ip()
    print(f"\nServing at http://{ip}:{PORT}/")
    print("Point your PS5 to this address via chh-local-installer.elf shortcuts.")
    print("Press Ctrl+C to stop.\n")

    with http.server.HTTPServer(("0.0.0.0", PORT), _SilentHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
