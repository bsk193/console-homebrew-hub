# Console Homebrew Hub — v2

Local exploit host for PS5 (and more consoles coming soon).

## Quick start

```bash
# 1. Clone exploit sources
python setup_exploits.py

# 2. Start the server (DNS + HTTPS)
sudo python chh-host.py
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

## Available Payloads

<!-- PAYLOADS_START -->

### Utilities

| Payload | Version | FW Range | Description | Last Updated | Source | Download |
| --- | --- | --- | --- | --- | --- | --- |
| **BackPork** | `0.1` | `—` | No description provided. | `2026-04-30` | [Source](https://github.com/BestPig/BackPork/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/ps5-backpork_0.1.elf) |
| **BFpilot** | `v0.4.4` | `—` | No description provided. | `2026-08-11` | [Source](https://github.com/ItsBlurf/BFpilot/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/bfpilot_v0.4.4.elf) |
| **BFpilot Installer** | `v0.4.3` | `—` | No description provided. | `2026-07-27` | [Source](https://github.com/ItsBlurf/BFpilot/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/bfpilot-launcher-installer_v0.4.3.elf) |
| **CHH Installer** | `v1.0.0` | `—` | Console Homebrew Hub installer — installs PS5 homescreen shortcuts pointing to CHH exploits on GitHub Pages. | `2026-08-18` | [Source](#) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/chh-installer_v1.0.0.elf) |
| **ELFArsenal** | `v1.6.22` | `—` | No description provided. | `2026-07-09` | [Source](https://github.com/bsk193/elf-arsenal-mirror/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/elf-arsenal_v1.6.22.elf) |
| **elfldr** | `v0.24` | `—` | No description provided. | `2026-08-02` | [Source](https://github.com/ps5-payload-dev/elfldr/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/elfldr-ps5_v0.24.elf) |
| **etaHEN** | `2.5B` | `—` | No description provided. | `2025-12-25` | [Source](https://github.com/etaHEN/etaHEN/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/etaHEN-2.5B.bin) |
| **ftpsrv** | `v0.21` | `—` | No description provided. | `2026-08-02` | [Source](https://github.com/ps5-payload-dev/ftpsrv/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/ftpsrv-ps5_v0.21.elf) |
| **ftpsrv DR** | `1.15-ng-stable` | `—` | No description provided. | `2026-04-08` | [Source](https://github.com/drakmor/ftpsrv/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/ftpsrv-ps5_1.15-ng-stable.elf) |
| **Garlic Save Manager** | `v1.7` | `—` | No description provided. | `2026-03-16` | [Source](https://github.com/earthonion/garlic-savemgr/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/garlic-savemgr_v1.7.elf) |
| **klogsrv** | `v0.9` | `—` | No description provided. | `2026-08-02` | [Source](https://github.com/ps5-payload-dev/klogsrv/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/klogsrv-ps5_v0.9.elf) |
| **KStuff** | `v1.6.7` | `—` | No description provided. | `2026-01-04` | [Source](https://github.com/EchoStretch/kstuff/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/kstuff_v1.6.7.elf) |
| **KStuff Lite** | `v1.10` | `—` | No description provided. | `2026-08-12` | [Source](https://github.com/EchoStretch/kstuff-lite/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/kstuff_v1.10.elf) |
| **KStuff Lite DR** | `1.2-dr-test1` | `—` | No description provided. | `2026-05-31` | [Source](https://github.com/drakmor/kstuff-lite/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/kstuff_1.2-dr-test1.elf) |
| **Lapy JB Daemon** | `v1.2` | `—` | No description provided. | `2026-06-01` | [Source](https://github.com/itsPLK/PS5-Lapy-JB-Daemon/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/lapy_jb_daemon-v1.2.elf) |
| **nanoDNS** | `0.4` | `—` | No description provided. | `2026-08-04` | [Source](https://github.com/drakmor/nanoDNS/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/nanodns_0.4.elf) |
| **NPFakeSignIn** | `1.1` | `—` | No description provided. | `2026-02-02` | [Source](https://github.com/earthonion/np-fake-signin/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/np-fake-signin-ps5_1.1.elf) |
| **onionHEN** | `v0.0.10` | `4.03–12.70` | PS5 homebrew enabler based on etaHEN. Supports firmware 4.03–12.7. | `2026-08-17` | [Source](https://github.com/aydencharles/onionHEN/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/OnionHEN.elf) |
| **Payload Manager** | `v0.5.1` | `—` | No description provided. | `2026-08-02` | [Source](https://github.com/itsPLK/ps5-payload-manager/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/pldmgr_v0.5.1.elf) |
| **Payload Manager X** | `v0.5.1.2x` | `—` | No description provided. | `2026-08-11` | [Source](https://github.com/bsk193/ps5-payload-manager-x/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/pldmgrx_v0.5.1.2x.elf) |
| **PegasusDL** | `v1.7.0` | `—` | No description provided. | `2026-06-24` | [Source](https://github.com/pegasus-ps5/pegasus-dl/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/pegasus_dl_v1.7.0.elf) |
| **PIZZA-HEN** | `v0.1` | `—` | All-in-one PS5 homebrew environment with KStuff, FTP, ps5debug-NG, plugin manager, and Itemzflow integration. | `2026-08-10` | [Source](https://github.com/Michele-M-Media/PIZZA-HEN/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/PIZZA-HEN-v0.1.elf) |
| **PS5 App Dumper** | `v1.11` | `—` | No description provided. | `2026-07-28` | [Source](https://github.com/EchoStretch/ps5-app-dumper/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/ps5-app-dumper_v1.11.elf) |
| **PS5 Linux Loader** | `v2.4` | `3.00–7.61` | No description provided. | `2026-07-06` | [Source](https://github.com/ps5-linux/ps5-linux-loader/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/ps5-linux-loader_v2.4.elf) |
| **PS5Debug** | `1.3.0` | `—` | No description provided. | `2026-06-21` | [Source](https://github.com/OpenSourcereR-dev/ps5debug-NG/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/ps5debug-NG_v1.3.0.elf) |
| **PS5GameCompressor** | `v1.0.3` | `—` | No description provided. | `2026-06-20` | [Source](https://github.com/juma-sayeh/PS5-Game-Compressor/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/game-compressor_v1.0.3.elf) |
| **PS5Upload** | `v5.3.2` | `—` | No description provided. | `2026-08-19` | [Source](https://github.com/phantomptr/ps5upload/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/ps5upload-5.3.2.elf) |
| **ShadowMountPlus** | `1.6beta16` | `—` | No description provided. | `2026-06-28` | [Source](https://github.com/drakmor/ShadowMountPlus/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/shadowmountplus_1.6beta16.elf) |
| **shsrv** | `v0.20` | `—` | No description provided. | `2026-08-02` | [Source](https://github.com/ps5-payload-dev/shsrv/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/shsrv-ps5_v0.20.elf) |
| **WebKit Autoloader** | `v0.3.0` | `—` | PS5 WebKit exploit autoloader installer ELF by itsPLK. | `2026-08-14` | [Source](https://github.com/itsPLK/ps5-webkit-autoloader/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/webkit-autoloader-installer_v0.3.0.elf) |
| **WebKit Autoloader X** | `v0.3.0.7x` | `—` | PS5 WebKit exploit autoloader X installer ELF by bsk193. | `2026-08-18` | [Source](https://github.com/bsk193/ps5-webkit-autoloader-x/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/webkit-autoloader-x-installer_v0.3.0.7x.elf) |
| **WebKit Autoloader X (Local)** | `v0.3.0.7x` | `—` | PS5 WebKit Autoloader X local installer ELF by bsk193 — installs a Jailbreak (Local) shortcut only. | `2026-08-18` | [Source](https://github.com/bsk193/ps5-webkit-autoloader-x/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/webkit-autoloader-x-local-installer_v0.3.0.7x.elf) |
| **websrv** | `v0.34` | `—` | No description provided. | `2026-08-02` | [Source](https://github.com/ps5-payload-dev/websrv/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/websrv-ps5_v0.34.elf) |
| **zftpd** | `v1.5.0` | `—` | No description provided. | `2026-06-14` | [Source](https://github.com/seregonwar/zftpd/releases) | [Download](https://github.com/bsk193/console-homebrew-hub/releases/latest/download/zftpd-ps5-v1.5.0.elf) |

<!-- PAYLOADS_END -->
