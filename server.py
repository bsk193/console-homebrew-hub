#!/usr/bin/env python3
"""
Exploit host server - serves the repo over HTTPS for local network use.

Usage:
  python server.py          # HTTPS on port 443 (may need admin/sudo)
  python server.py 8443     # HTTPS on port 8443 (no root needed)
  python server.py 8080 --http  # Plain HTTP (some exploits may need HTTPS)

Generate a self-signed cert first if you don't have one:
  openssl req -x509 -newkey rsa:2048 -keyout server.pem -out server.pem -days 365 -nodes -subj "/CN=exploit-host"
"""

import http.server
import ssl
import os
import sys
import socket

SERVE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 443
USE_HTTP = False

for arg in sys.argv[1:]:
    if arg == '--http':
        USE_HTTP = True
    elif arg.isdigit():
        PORT = int(arg)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.254.254.254', 1))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print('[%s] %s' % (self.address_string(), fmt % args))

os.chdir(SERVE_DIR)
httpd = http.server.HTTPServer(('0.0.0.0', PORT), Handler)

if not USE_HTTP:
    CERT = os.path.join(SERVE_DIR, 'server.pem')
    if not os.path.exists(CERT):
        # Try the cert bundled with the CSSFontFace exploit
        alt = os.path.join(SERVE_DIR, 'exploits', 'css-font-face', 'localhost.pem')
        if os.path.exists(alt):
            CERT = alt
        else:
            print('ERROR: No cert found. Generate one with:')
            print('  openssl req -x509 -newkey rsa:2048 -keyout server.pem -out server.pem -days 365 -nodes -subj "/CN=exploit-host"')
            sys.exit(1)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    scheme = 'https'
else:
    scheme = 'http'

ip = get_local_ip()
print('Exploit host running.')
print('  Exploit index : %s://%s:%d/exploits/' % (scheme, ip, PORT))
print('  Payload mirror: %s://%s:%d/' % (scheme, ip, PORT))
print('  Press Ctrl+C to stop.')

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print('\nStopped.')
