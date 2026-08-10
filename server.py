#!/usr/bin/env python3
"""
Exploit host server - serves the repo over HTTPS for local network use.

Usage:
  python server.py          # HTTPS on port 443 (may need admin/sudo)
  python server.py 8443     # HTTPS on port 8443 (no root needed)
  python server.py 8080 --http  # Plain HTTP
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

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print('[%s] %s' % (self.address_string(), fmt % args))

os.chdir(SERVE_DIR)
httpd = http.server.HTTPServer(('0.0.0.0', PORT), Handler)

if not USE_HTTP:
    CERT = os.path.join(SERVE_DIR, 'server.pem')
    if not os.path.exists(CERT):
        alt = os.path.join(SERVE_DIR, 'exploits', 'css-font-face', 'localhost.pem')
        if os.path.exists(alt):
            CERT = alt
        elif not generate_cert(CERT):
            print('WARNING: Could not generate a certificate (cryptography package missing).')
            print('  Install it with:  pip install cryptography')
            print('  Or run HTTP mode: python server.py %d --http' % PORT)
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
