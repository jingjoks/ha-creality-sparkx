# Creality SPARKX for Home Assistant

Local, cloud-free Home Assistant integration for the **Creality SPARKX i7**
(and likely other recent Creality printers that expose the same local
WebSocket API — see [Compatibility](#compatibility) below).

No account, no cloud, no API key. The printer streams its own state over a
plain WebSocket on the local network and this integration just listens.

**✅ Tested and confirmed working** on a real Creality SPARKX i7 — live
temperature sensors update in real time, entities register correctly, no
errors on setup.

## Features

- **Live sensors** — nozzle/bed temperature (current + target), print
  progress, current layer / total layers, current filename, elapsed and
  remaining print time, print state (idle/printing/paused/completed/error),
  fan speeds.
- **Lifetime stats** — total material used, total print time (disabled by
  default, enable in entity settings if you want them).
- **Chamber light switch** — turn the printer's light on/off from HA.
  ⚠️ Confirmed that the printer silently ignores this command while a print
  job is actively running (verified by testing the raw WebSocket command
  directly against the printer, bypassing Home Assistant entirely — the
  light state simply doesn't change and the printer's own confirmation
  response is absent). This appears to be a firmware-level restriction, not
  a bug in this integration. Works normally while idle.
- **Binary sensors** — filament presence, problem/error flag, and a
  connectivity sensor so automations can react to the printer going offline.
- **Local push** — no polling. The printer pushes updates as they happen, so
  state changes show up in HA almost instantly.
- **Auto-reconnect** — if the printer reboots, changes networks, or HA
  restarts, the integration keeps retrying the connection in the
  background.

## Installation

### Via HACS (custom repository)

1. HACS → Integrations → ⋮ (top right) → **Custom repositories**.
2. Add this repository URL, category **Integration**.
3. Search for **Creality SPARKX**, install, then restart Home Assistant.

### Manual

1. Copy `custom_components/creality_sparkx` into your Home Assistant
   `config/custom_components/` folder.
2. Restart Home Assistant.

## Configuration

Settings → Devices & Services → **Add Integration** → search **Creality
SPARKX** → enter the printer's local IP address (e.g. `192.168.1.97`).

The integration verifies connectivity by calling the printer's `/info`
endpoint before finishing setup, so you'll get an immediate error if the IP
is wrong or the printer isn't reachable.

## Example automation

```yaml
alias: "3D print finished"
trigger:
  - platform: state
    entity_id: sensor.i7_9120_print_state
    to: "completed"
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "🎉 Print finished"
      message: "{{ state_attr('sensor.i7_9120_current_file','friendly_name') }}"
```

## Compatibility

This was built and tested against a **Creality SPARKX i7** (internal model
code `F022`, firmware `1.1.5.8`), which exposes:

- `GET /info` — device identity (mac, model, serial, firmware version), no
  auth required.
- `WS /ws` — a plain WebSocket, no auth, no handshake payload needed. The
  first message is a full state snapshot; later messages are partial
  updates (only the keys that changed). Sending a JSON object with the
  key(s) you want to change (e.g. `{"lightSw": 0}`) issues a command.

Several community integrations for Creality **K1 / K1 Max / K1C / K2**
(`ha_creality_ws`, `hass_creality_k1`, `ha-creality-lan`, etc.) describe a
very similar JSON schema (`nozzleTemp`, `bedTemp0`, `printProgress`,
`cfsConnect`, ...), but those printers expose it on **port 9999** rather
than the plain HTTP port used here. If you have a printer that matches that
port/schema, this integration probably won't connect out of the box — try
one of those projects instead. If your printer uses port 80 like the
SPARKX i7, this should work; please open an issue either way with your
`/info` output so compatibility can be tracked.

## Known limitations

- **Commands may be ignored mid-print.** The chamber light switch (and
  possibly other control commands not yet implemented here) appear to be
  rejected by the printer's firmware while a print job is actively running.
  The WebSocket still responds with routine status pushes, but not a
  confirmation of the requested change, and the actual state doesn't move.
  This was confirmed by testing the raw `{"lightSw": 1}` command directly
  against the printer over a plain WebSocket connection, with the same
  result — so it's a printer-side restriction, not something this
  integration can work around. Try again once the print finishes or the
  printer is idle.

## Disclaimer

This is an independent, community project and is not affiliated with or
endorsed by Creality. It was built by reverse-engineering the printer's own
local API traffic — no cloud account or vendor documentation was used.
Printer control (currently just the light switch) is exposed on a best-effort
basis; please don't rely on this integration for anything safety-critical.

## License

MIT — see [LICENSE](LICENSE).
