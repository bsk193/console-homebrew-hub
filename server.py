#!/usr/bin/env python3
"""
Exploit host server.

Usage:
  sudo python server.py          # DNS:53 + HTTPS:443 + HTTPS:6969 (recommended)
  sudo python server.py 443      # DNS:53 + HTTPS:443 only
  python server.py 6969          # HTTPS:6969 only (no sudo; DNS/443 skipped if permission denied)
  python server.py 8080 --http   # Plain HTTP on a custom port

PS5 DNS trick (Health Guide / User Manual entry point):
  1. sudo python server.py
  2. On PS5: Settings > Network > Set Up Internet > Custom > DNS Manual
     Primary DNS: <this machine's IP shown on startup>
  3. PS5 User Guide / Health & Safety redirects to this machine — exploit loads automatically.

Direct access (no DNS trick):
  On PS5 browser: https://<ip>:6969   (accept the certificate warning)
"""

import http.server
import ssl
import os
import sys
import socket
import struct
import threading

SERVE_DIR = os.path.dirname(os.path.abspath(__file__))
DNS_PORT = 53
USE_HTTP = False

# Parse args: collect port numbers and flags
requested_ports = []
for arg in sys.argv[1:]:
    if arg == '--http':
        USE_HTTP = True
    elif arg == '--no-dns':
        pass  # reserved for future use; DNS failure is already non-fatal
    elif arg.isdigit():
        requested_ports.append(int(arg))

# Default: run on both 443 (DNS trick) and 6969 (direct access)
WEB_PORTS = requested_ports if requested_ports else [443, 6969]


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.254.254.254', 1))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


def generate_cert(path):
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import datetime

        print('Generating self-signed certificate...')
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u'exploit-host')])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName(u'localhost')]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )
        with open(path, 'wb') as f:
            f.write(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            ))
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        print('Certificate saved to %s' % path)
        return True
    except ImportError:
        return False


def build_dns_response(data, local_ip):
    if len(data) < 12:
        return None
    tid = data[:2]
    flags = struct.pack('>H', 0x8180)
    qdcount = data[4:6]
    ancount = struct.pack('>H', 1)
    nscount = struct.pack('>H', 0)
    arcount = struct.pack('>H', 0)
    header = tid + flags + qdcount + ancount + nscount + arcount
    question = data[12:]
    answer = (
        struct.pack('>H', 0xC00C) +
        struct.pack('>H', 1) +
        struct.pack('>H', 1) +
        struct.pack('>I', 10) +
        struct.pack('>H', 4) +
        socket.inet_aton(local_ip)
    )
    return header + question + answer


def run_dns(local_ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(('0.0.0.0', port))
        print('[DNS] Listening on port %d — all queries resolve to %s' % (port, local_ip))
        while True:
            try:
                data, addr = sock.recvfrom(512)
                resp = build_dns_response(data, local_ip)
                if resp:
                    sock.sendto(resp, addr)
            except Exception as e:
                print('[DNS error] %s' % e)
    except PermissionError:
        print('[DNS] WARNING: Cannot bind port %d — run with sudo to enable DNS trick.' % port)
    except OSError as e:
        print('[DNS] WARNING: Port %d: %s' % (port, e))
    finally:
        sock.close()


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # PS5 User Guide / Health Guide DNS intercept.
        # PS5 visits https://manuals.playstation.net/document/{locale}/ps5/…
        # DNS resolves to this server; we redirect to our local intercept page.
        # Anchored to ^/document/ so /exploits/slopkit/document/… is not caught.
        import re
        if re.match(r'^/document/[^/]+/ps5(/|$)', self.path):
            self.send_response(302)
            self.send_header('Location', '/ps5/')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            return
        super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def log_message(self, fmt, *args):
        print('[%s] %s' % (self.address_string(), fmt % args))


os.chdir(SERVE_DIR)
ip = get_local_ip()
scheme = 'http' if USE_HTTP else 'https'

# Resolve TLS certificate once (shared across all web server instances)
ssl_ctx = None
if not USE_HTTP:
    CERT = os.path.join(SERVE_DIR, 'server.pem')
    if not os.path.exists(CERT):
        alt = os.path.join(SERVE_DIR, 'exploits', 'css-font-face', 'localhost.pem')
        if os.path.exists(alt):
            CERT = alt
        elif not generate_cert(CERT):
            print('WARNING: Could not generate a certificate (cryptography package missing).')
            print('  Install it with:  pip install cryptography')
            print('  Or run HTTP mode: python server.py 6969 --http')
            sys.exit(1)
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(CERT)


def start_web_server(port, is_main=False):
    try:
        httpd = http.server.HTTPServer(('0.0.0.0', port), Handler)
        if ssl_ctx:
            httpd.socket = ssl_ctx.wrap_socket(httpd.socket, server_side=True)
        print('[Web] %s://%s:%d/' % (scheme, ip, port))
        if is_main:
            httpd.serve_forever()
        else:
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
    except PermissionError:
        print('[Web] WARNING: Cannot bind port %d — run with sudo.' % port)
    except OSError as e:
        print('[Web] WARNING: Port %d: %s' % (port, e))


# Start DNS (always; non-fatal if no permission)
dns_thread = threading.Thread(target=run_dns, args=(ip, DNS_PORT), daemon=True)
dns_thread.start()

print('Exploit host starting.')
print('  Local IP : %s' % ip)
print('  DNS      : %s:%d  ← set as Primary DNS on PS5 for Health Guide trick' % (ip, DNS_PORT))

# Start all web ports except the last one in background threads
for port in WEB_PORTS[:-1]:
    start_web_server(port, is_main=False)

print('  Press Ctrl+C to stop.')

try:
    start_web_server(WEB_PORTS[-1], is_main=True)
except KeyboardInterrupt:
    print('\nStopped.')
