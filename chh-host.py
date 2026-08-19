#!/usr/bin/env python3
"""Console Homebrew Hub — Local Host Server

Three services start together:
  DNS   port 53    — spoofs manuals.playstation.net → this PC; NXDOMAIN for everything else
  HTTPS port 443   — serves exploit pages (PS5 User's Guide / manuals trick)
  HTTP  port 6969 — serves ELF payload files + exploit pages for local shortcuts

Usage:
  sudo python chh-host.py            # guided mode (recommended)
  sudo python chh-host.py --verbose  # detailed per-request logging
  sudo python chh-host.py --no-dns   # skip DNS (use external DNS tool)
  python chh-host.py --no-dns --no-https  # HTTP 6969 only, no elevated privileges needed

PS5 setup:
  1. Run: sudo python chh-host.py
  2. PS5: Settings > Network > Setup > Custom > DNS Manual
     Primary DNS: <IP shown on startup>
  3. Open User's Guide on PS5 — exploit loads automatically via the manuals trick.
     Or use the CHH Local Installer shortcut to go straight to port 6969.
"""

import argparse
import errno
import io
import mimetypes
import os
import re
import socket
import socketserver
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# ── Configuration ─────────────────────────────────────────────────────────────

DNS_TARGET   = "manuals.playstation.net"
DNS_TTL      = 300
DNS_PORT     = 53
HTTPS_PORT   = 443
HTTP_PORT    = 6969

# GitHub repo and release URLs
CHH_REPO    = "bsk193/console-homebrew-hub"
CHH_RELEASE = f"https://github.com/{CHH_REPO}/releases/latest/download"
CHH_ZIP     = f"https://github.com/{CHH_REPO}/archive/refs/heads/main.zip"
REQUIRED_ELFS = ["pldmgrx.elf", "chh-shortcut.elf"]

SERVE_DIR = os.path.dirname(os.path.abspath(__file__))

mimetypes.add_type("text/cache-manifest", ".appcache")

# ── ANSI colours ──────────────────────────────────────────────────────────────

def _init_color():
    if not sys.stdout.isatty():
        return False
    if os.name == "nt":
        import ctypes
        ENABLE_VT = 0x0004
        k32 = ctypes.windll.kernel32
        for h in (-11, -12):
            handle = k32.GetStdHandle(h)
            mode   = ctypes.c_ulong()
            if k32.GetConsoleMode(handle, ctypes.byref(mode)):
                k32.SetConsoleMode(handle, mode.value | ENABLE_VT)
    return True

COLOR = _init_color()

def _s(text, *codes):
    if not COLOR:
        return text
    return "\033[" + ";".join(str(c) for c in codes) + "m" + text + "\033[0m"

def tag(text):
    return text.replace("[+]", _s("[+]", 32)).replace("[-]", _s("[-]", 31))

# ── Banner / splash ───────────────────────────────────────────────────────────

def banner():
    W = 46
    row = lambda t: "   │" + t.center(W) + "│"
    lines = [
        "",
        "   ┌" + "─" * W + "┐",
        row("CONSOLE HOMEBREW HUB"),
        row("LOCAL HOST"),
        row("github.com/bsk193/console-homebrew-hub"),
        "   └" + "─" * W + "┘",
    ]
    return _s("\n".join(lines), 36)

# ── Helpers ───────────────────────────────────────────────────────────────────

def detect_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()

def _bind_hint(service, port, exc):
    if isinstance(exc, PermissionError):
        return (
            f"    {service} port {port} needs elevated privileges. "
            "On Linux/macOS run with sudo; on Windows run as Administrator."
        )
    if getattr(exc, "errno", None) == errno.EADDRINUSE:
        return (
            f"    Port {port} is already in use. Stop whatever is holding it, "
            "or pass --no-dns / --no-https to skip privileged ports."
        )
    return ""

def download_if_missing(filename, url, verbose=False):
    path = os.path.join(SERVE_DIR, filename)
    if os.path.exists(path):
        if verbose:
            print(tag(f"[+] {filename} already present."))
        return True
    print(tag(f"[+] Downloading {filename}..."))
    try:
        urllib.request.urlretrieve(url, path)
        print(tag(f"[+]   OK ({os.path.getsize(path):,} bytes)"))
        return True
    except Exception as e:
        print(tag(f"[-]   Could not download {filename}: {e}"))
        print(f"    Get manually: {url}")
        return False


def _needs_web_content():
    """Check if the web content (HTML pages, exploit cores) is present."""
    markers = [
        os.path.join(SERVE_DIR, "index.html"),
        os.path.join(SERVE_DIR, "ps5", "index.html"),
        os.path.join(SERVE_DIR, "ps5", "exploits", "slopkit", "index.html"),
    ]
    return not all(os.path.exists(m) for m in markers)


def download_web_content():
    """Download the full CHH repo as a ZIP and extract web content into SERVE_DIR."""
    import zipfile

    print(tag("[+] Web content not found — downloading from GitHub..."))
    zip_path = os.path.join(SERVE_DIR, "_chh-repo.zip")
    try:
        urllib.request.urlretrieve(CHH_ZIP, zip_path)
    except Exception as e:
        print(tag(f"[-] Could not download repo: {e}"))
        print(f"    Clone manually: git clone https://github.com/{CHH_REPO}.git")
        return False

    try:
        with zipfile.ZipFile(zip_path) as zf:
            prefix = zf.namelist()[0]  # e.g. "console-homebrew-hub-main/"
            count = 0
            for entry in zf.namelist():
                if entry.endswith("/"):
                    continue
                rel = entry[len(prefix):]
                # Skip CI, build files, and source — only extract web content
                if rel.startswith((".github/", "chh-src/", "tools/")):
                    continue
                if rel in ("chh-host.py",):
                    continue
                if ".." in rel.split("/"):
                    continue
                dest = os.path.realpath(os.path.join(SERVE_DIR, rel.replace("/", os.sep)))
                if not dest.startswith(os.path.realpath(SERVE_DIR) + os.sep):
                    continue
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zf.open(entry) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                count += 1
            print(tag(f"[+]   Extracted {count} files."))
    except Exception as e:
        print(tag(f"[-] Could not extract repo ZIP: {e}"))
        return False
    finally:
        try:
            os.remove(zip_path)
        except OSError:
            pass

    return True

# ── Self-signed TLS certificate ───────────────────────────────────────────────

def _gen_cert_openssl(cert_path, key_path):
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-nodes", "-days", "3650", "-sha256",
            "-keyout", key_path, "-out", cert_path,
            "-subj", f"/CN={DNS_TARGET}",
        ],
        check=True, capture_output=True,
    )

def _gen_cert_cryptography(cert_path, key_path):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import datetime

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, DNS_TARGET)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(DNS_TARGET)]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

def get_tls_context():
    """Return an ssl.SSLContext with a self-signed cert for DNS_TARGET."""
    cached_cert = os.path.join(SERVE_DIR, "chh-server.pem")
    cached_key  = os.path.join(SERVE_DIR, "chh-server.key")

    # Look for an existing cert in the exploit core dirs
    for alt in [
        os.path.join(SERVE_DIR, "ps5", "exploits", "umtx",    "core", "localhost.pem"),
        os.path.join(SERVE_DIR, "ps5", "exploits", "slopkit",  "core", "localhost.pem"),
    ]:
        if os.path.exists(alt):
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(alt)
            print(tag(f"[+] TLS: using existing cert {alt}"))
            return ctx

    if not os.path.exists(cached_cert):
        print(tag("[+] Generating self-signed TLS certificate..."))
        try:
            _gen_cert_cryptography(cached_cert, cached_key)
        except ImportError:
            try:
                _gen_cert_openssl(cached_cert, cached_key)
            except (OSError, subprocess.CalledProcessError) as e:
                print(tag(f"[-] Could not generate TLS certificate: {e}"))
                print("    Install openssl or: pip install cryptography")
                return None

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    if os.path.exists(cached_key):
        ctx.load_cert_chain(certfile=cached_cert, keyfile=cached_key)
    else:
        ctx.load_cert_chain(certfile=cached_cert)
    print(tag("[+] TLS certificate ready."))
    return ctx

# ── DNS server ────────────────────────────────────────────────────────────────

def _parse_dns_name(data, offset):
    labels = []
    while offset < len(data):
        length = data[offset]
        if length == 0:
            return ".".join(labels).lower(), offset + 1
        if length & 0xC0 == 0xC0:
            return None, None  # compressed pointer — skip
        offset += 1
        if offset + length > len(data):
            return None, None
        labels.append(data[offset:offset + length].decode("ascii", "replace"))
        offset += length
    return None, None

def _dns_response(data, ip=None):
    if len(data) < 12:
        return None
    qid = data[:2]
    if ip:
        flags  = struct.pack(">H", 0x8180)   # QR + RD + RA
        ancount = struct.pack(">H", 1)
        answer  = (b"\xc0\x0c"
                   + struct.pack(">HHIH", 1, 1, DNS_TTL, 4)
                   + socket.inet_aton(ip))
    else:
        flags  = struct.pack(">H", 0x8183)   # QR + RD + RA + NXDOMAIN
        ancount = struct.pack(">H", 0)
        answer  = b""
    header = qid + flags + data[4:6] + ancount + b"\x00\x00\x00\x00"
    return header + data[12:] + answer

class _DNSHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        name, _ = _parse_dns_name(data, 12)
        if name is None:
            return
        server = self.server
        if name == DNS_TARGET.lower():
            resp = _dns_response(data, server.local_ip)
            server.log_fn(_s(f"[DNS]  {name} -> {server.local_ip}", 36))
            server.guide.on_connection()
        else:
            resp = _dns_response(data)
            if server.verbose:
                server.log_fn(_s(f"[DNS]  {name} -> NXDOMAIN", 31))
        if resp:
            sock.sendto(resp, self.client_address)

class DNSServer(socketserver.ThreadingUDPServer):
    allow_reuse_address = True
    def __init__(self, address, local_ip, log_fn=print, verbose=False, guide=None):
        self.local_ip = local_ip
        self.log_fn   = log_fn
        self.verbose  = verbose
        self.guide    = guide
        super().__init__(address, _DNSHandler)

# ── Guided status messages ────────────────────────────────────────────────────

class GuideStatus:
    """Prints one-shot messages when the PS5 first connects and when the
    exploit page is served — mirrors the bsk193 host.py guided-mode UX."""

    def __init__(self, logger=print):
        self.logger    = logger
        self.connected = False
        self.served    = False
        self._lock     = threading.Lock()

    def on_connection(self):
        with self._lock:
            if self.connected:
                return
            self.connected = True
        self.logger(tag(
            "\n[+] PS5 connection detected.\n"
            "    Open the User's Guide on your PS5\n"
            "    (Settings -> User's Guide) to trigger the exploit.\n"
            "    Or navigate to your CHH local shortcut on port 6969.\n"
        ))

    def on_exploit_served(self):
        with self._lock:
            if self.served:
                return
            self.served = True
        self.logger(tag(
            "\n[+] Exploit page served.\n"
            "    If the exploit succeeded, pldmgrx.elf will load automatically.\n"
            "    You can now close this host and reset your PS5 DNS\n"
            "    (otherwise your PS5 won't be able to reach the internet).\n"
        ))

# ── HTTP/HTTPS request handler ────────────────────────────────────────────────

class ChhHandler(SimpleHTTPRequestHandler):
    """Serves files from SERVE_DIR with path-rewrite rules:

      - /document/<locale>/ps5/...  → redirect to /ps5/ (firmware detection page)
        Detection page routes to the right exploit wrapper; wrapper defaults to install
        mode (chh-shortcut.elf). After the shortcut is installed the user can run any
        exploit with ?autoload=pldmgrx.elf to load Payload Manager X.

      - /console-homebrew-hub/<rest> → /<rest>
        The CHH wrapper pages embed exploit cores in iframes using their GitHub Pages
        absolute path (/console-homebrew-hub/...).  Strip the prefix so those requests
        resolve to the local repo files.

      - everything else → static file server from SERVE_DIR
    """

    def __init__(self, *args, verbose=False, guide=None, **kwargs):
        self._verbose = verbose
        self._guide   = guide
        kwargs.setdefault("directory", SERVE_DIR)
        super().__init__(*args, **kwargs)

    def _rewrite(self):
        # 1. Manuals trick: redirect to CHH wrapper with autoload param
        if re.match(r"^/document/[^/]+/ps5(/|$)", self.path):
            return "redirect", "/ps5/"

        # 2. Strip /console-homebrew-hub prefix (GitHub Pages base path → local root)
        if self.path.startswith("/console-homebrew-hub/"):
            self.path = self.path[len("/console-homebrew-hub"):]  # keep leading /
            return "rewrite", None

        return None, None

    def do_GET(self):
        self._guide.on_connection()
        action, target = self._rewrite()
        if action == "redirect":
            self._guide.on_exploit_served()
            self.send_response(302)
            self.send_header("Location", target)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self):
        if not self.path.endswith(('.elf', '.appcache')):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma",        "no-cache")
            self.send_header("Expires",       "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        if self._verbose:
            print(_s("[HTTP] " + (fmt % args), 34))

def _make_handler(verbose, guide):
    def factory(*args, **kwargs):
        return ChhHandler(*args, verbose=verbose, guide=guide, **kwargs)
    return factory

# ── Server startup ─────────────────────────────────────────────────────────────

def start_https(port, tls_ctx, handler_factory, verbose):
    try:
        httpd = ThreadingHTTPServer(("0.0.0.0", port), handler_factory)
        httpd.socket = tls_ctx.wrap_socket(httpd.socket, server_side=True)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        print(tag(f"[+] HTTPS server on TCP {port}"))
        return httpd
    except OSError as exc:
        print(tag(f"[-] Could not bind HTTPS port {port}: {exc}"))
        hint = _bind_hint("HTTPS", port, exc)
        if hint:
            print(_s(hint, 2))
        return None

def start_http(port, handler_factory, verbose):
    try:
        httpd = ThreadingHTTPServer(("0.0.0.0", port), handler_factory)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        print(tag(f"[+] HTTP  server on TCP {port}"))
        return httpd
    except OSError as exc:
        print(tag(f"[-] Could not bind HTTP port {port}: {exc}"))
        hint = _bind_hint("HTTP", port, exc)
        if hint:
            print(_s(hint, 2))
        return None

# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="chh-host.py",
        description="CHH local host: DNS spoofer + HTTPS/HTTP servers for PS5 exploit delivery.",
    )
    p.add_argument("--ip",         default=None,     help="Override local IP (auto-detected by default).")
    p.add_argument("--dns-port",   type=int, default=DNS_PORT,   help=f"DNS UDP port (default: {DNS_PORT}).")
    p.add_argument("--https-port", type=int, default=HTTPS_PORT, help=f"HTTPS port (default: {HTTPS_PORT}).")
    p.add_argument("--http-port",  type=int, default=HTTP_PORT,  help=f"HTTP port (default: {HTTP_PORT}).")
    p.add_argument("--no-dns",     action="store_true", help="Disable DNS server.")
    p.add_argument("--no-https",   action="store_true", help="Disable HTTPS server (skips cert generation).")
    p.add_argument("--verbose",    action="store_true", help="Print per-request DNS/HTTP logs.")
    p.add_argument("--no-color",   action="store_true", help="Disable ANSI color output.")
    return p.parse_args(argv)

# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv=None):
    args = parse_args(argv)

    if args.no_color:
        global COLOR
        COLOR = False

    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass

    ip = args.ip or detect_local_ip()

    print(banner())

    # Download web content (HTML, JS, exploit cores) if not present
    if _needs_web_content():
        if not download_web_content():
            print(tag("[-] Cannot start without web content."))
            return 1

    # Download required ELF files if missing
    for elf in REQUIRED_ELFS:
        download_if_missing(elf, f"{CHH_RELEASE}/{elf}")

    guide = GuideStatus(logger=print)

    # DNS
    dns = None
    if not args.no_dns:
        try:
            dns = DNSServer(
                ("0.0.0.0", args.dns_port),
                local_ip=ip,
                log_fn=print if args.verbose else (lambda *a, **k: None),
                verbose=args.verbose,
                guide=guide,
            )
            threading.Thread(target=dns.serve_forever, daemon=True).start()
            print(tag(f"[+] DNS   server on UDP {args.dns_port}  (spoofing '{DNS_TARGET}' -> {ip})"))
        except OSError as exc:
            print(tag(f"[-] Could not bind DNS port {args.dns_port}: {exc}"))
            _bind_hint("DNS", args.dns_port, exc)

    handler = _make_handler(args.verbose, guide)

    # HTTPS 443 (manuals / User's Guide trick)
    httpsd = None
    if not args.no_https:
        tls_ctx = get_tls_context()
        if tls_ctx:
            httpsd = start_https(args.https_port, tls_ctx, handler, args.verbose)

    # HTTP 6969 (ELF payload server + exploit pages for local shortcuts)
    httpd = start_http(args.http_port, handler, args.verbose)

    if not dns and not httpsd and not httpd:
        print(tag("[-] No servers could be started."))
        return 1

    print(tag(f"\n[+] Set your PS5 DNS to {_s(ip, 1, 33)}."))
    print(tag(
        f"[+] Waiting for PS5 connection...\n"
        f"    Exploit pages : https://{ip}:{args.https_port}/ps5/\n"
        f"    Payload ELFs  : http://{ip}:{args.http_port}/\n"
        f"    Manuals trick : set PS5 Primary DNS to {ip}, then open User's Guide.\n"
    ))
    print("    Press Ctrl+C to stop.\n")

    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        print(tag("\n[-] Shutting down."))
        if dns:
            dns.shutdown(); dns.server_close()
        if httpsd:
            httpsd.shutdown(); httpsd.server_close()
        if httpd:
            httpd.shutdown(); httpd.server_close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
