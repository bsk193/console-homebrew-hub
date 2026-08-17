# Console Homebrew Hub — v2

Local exploit host for PS5 (and more consoles coming soon).

## Quick start

```bash
# 1. Clone exploit sources
python setup_exploits.py

# 2. Start the server (DNS + HTTPS)
sudo python server.py
```

Then on your PS5:
- **Settings → Network → Set Up Internet Connection → Custom → DNS Manual**
- Set Primary DNS to the IP shown in the server output
- Open the PS5 User Guide / Health & Safety — it will redirect to CHH automatically

Or navigate directly to `https://<your-ip>:6969` in the PS5 browser.

## PS5 Exploit Support

| Firmware | Exploit | Loader |
|---|---|---|
| 1.00–5.50 | UMTX | elfldr |
| 3.00–4.51 | IPV6 (+ UMTX) | elfldr |
| 9.00–12.00 | Slopkit | elfldr |

## Payload Mirror

The `payloads.json` file tracks all mirrored payloads. To update:

```bash
python update_payloads.py
```

The GitHub Actions `update_mirror.yml` workflow runs this daily automatically.

## Exploit Sources

- [umtx2](https://github.com/idlesauce/umtx2) by idlesauce
- [PS5-Exploit-Host](https://github.com/idlesauce/PS5-Exploit-Host) by idlesauce
- [slopkit](https://github.com/jordyidk/slopkit) by jordyidk
- [ps5-webkit-autoloader-x](https://github.com/bsk193/ps5-webkit-autoloader-x) by bsk193
