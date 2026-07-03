# Bridger — Hermes Remote Browser Control

Control your Windows Chrome browser from Hermes (Linux server) via CDP.

## Architecture

```
Windows (Chrome CDP) ──TCP──→ Linux Server (Hermes)
      :9222                    :5099 (bridge)
                               :5100 (API)
```

## Quick Start

### On Windows (Chrome + CDP)

1. Start Chrome with remote debugging:
```powershell
& "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --remote-allow-origins=* `
  --user-data-dir="$env:USERPROFILE\.hermes-chrome-debug" `
  --no-first-run `
  --no-default-browser-check
```

2. Verify CDP works:
```powershell
curl.exe http://localhost:9222/json/version
```

3. Install dependencies:
```powershell
pip install websockets
```

4. Edit `cdp_bridge.py` — update `CDP_URL` with your `webSocketDebuggerUrl` from step 2

5. Run the bridge:
```powershell
python cdp_bridge.py
```

### On Linux Server (Hermes)

The bridge server runs automatically when the Windows client connects to `76.13.18.146:5099`.

## Files

| File | Purpose |
|------|---------|
| `cdp_bridge.py` | 🏆 **Main** — CDP bridge (recommended) |
| `bridge_client.py` | ⚠️ Playwright-based bridge (legacy) |
| `bridge_server.py` | Server component (runs on Linux) |
| `browser_api.py` | HTTP API server for local browser control |

## Troubleshooting

- **"Host header is specified"** — Add `--remote-allow-origins=*` to Chrome launch flags
- **Timeout** — Check firewall, ensure tunnel ports are open
- **CDP URL changes** — Chrome generates a new `webSocketDebuggerUrl` on each restart
