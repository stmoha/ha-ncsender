# ha-ncsender — working notes for Claude Code

Native Home Assistant integration for ncSender (CNC sender for grblHAL / Sienci SLB-EXT).
In the HACS default store since Oct 2026. Owner: stmoha. Author of ncSender: Francis (siganberg/ncSender).

## Layout
- `custom_components/ncsender/` — the integration. `client.py` is the core: a WebSocket client that
  mirrors ncSender's state stream into a derived snapshot (`client.data`) that all entities read.
  Platforms: sensor, binary_sensor, button, switch (switch added in v0.4.0).
- `tests/` — HA harness tests (`pytest-homeassistant-custom-component`). The harness needs Python 3.13
  and HA ≥ 2025.1; when the sandbox can't run it, test `client.py` standalone against a fake
  aiohttp server (pattern in git history: PR #1, PR #3) and syntax-check the rest with `ast.parse`.
- `blueprints/`, `examples/` — community-contributed HA blueprints (PR #2, tmuka). No integration code.
- `docs/ROADMAP.md` — what's in flight and what's next. Read it before starting new work.

## How ncSender talks (verified against siganberg/ncSender source, community edition)
- WS at `ws://host:8090/?product=...`. Envelope `{"type": ..., "data": ...}`. On connect the server
  sends the **full ServerState**; after that only **shallow deltas** — nested objects (`machineState`,
  `jobLoaded`) contain only changed keys; `jobLoaded` may become `null`. `client._merge_delta` mirrors
  ncSender's `StateDeltaTracker`. Don't deep-merge; don't treat a missing key as a change.
- `cnc-command-result` broadcasts every command with `status` success/error/flushed. We parse
  acknowledged (`success`) commands for things ncSender's own state doesn't track reliably.
- REST: `/api/health`, `/api/server-state`, `/api/send-command` (`{"command","sourceId"}`),
  `/api/gcode-job/{pause,resume,stop}`, `/api/tools`. **No auth of any kind** — anyone on the LAN
  can read state and send commands. Never add credential plumbing that implies otherwise.

## Quirks we work around — do not "simplify" these away
- **Stale accessory flags.** grblHAL omits the `A:` status field when no accessory is on, and ncSender
  *preserves* `spindleActive`/`floodCoolant`/`mistCoolant` when the field is absent, so the final
  all-off transition is lost. Spindle: require nonzero RPM alongside the flag. Coolant: track M7/M8/M9/
  M2/M30/soft-reset from the command stream (`coolant` shadow state); a flag value appearing *in a
  delta* is a real transition and overrides the shadow.
- **Spindle vs laser** share the same fields. Laser = active with S ≤ `laser_max_s` (default 1000) and
  no RPM feedback (PWM has none); VFD spindle = anything else. Coast-down (target 0, actual > 0) is
  still "spindle on" — correct for chiller/dust automations.
- **ncSender Pro reports `job_status: error` on a successful completion** and progress stalls ~95%.
  Don't key completion on `completed` or `progress == 100`. The user's helper uses
  `current_line >= total_lines - 5` with status not running/paused. Treat `error` with the processor
  at EOF as success. (Reported upstream; may change.)
- **Pro doesn't set `isToolChanging` for ATC swaps** and the reported tool number may not change.
  `sensor.ncsender_tool_change` (timestamp, v0.3.1) fires on every acknowledged **M6** instead —
  before the swap. Trigger automations on its state change, `not_from: [unknown, unavailable]`.
- **Aux outputs.** ncSender tracks `M64 Pn`/`M65 Pn` itself and publishes ON pins in
  `machineState.outputPinsState`. grblHAL rejects `P >= ioports_unclaimed(...)` with error:39, so only
  the board's real unclaimed outputs work (single digits on SLB-EXT) — "virtual" pins beyond that don't.
- **Telemetry pacing.** Positions/RPM/feed/progress are throttled (`telemetry_interval`, default 5 s,
  trailing flush so the last value of a burst always lands) and quantized, to keep the HA recorder
  small. State-like keys (`IMMEDIATE_KEYS`) always push at once. Never put a high-churn value in a
  sensor's attributes (it rewrites the whole entity every tick).

## Conventions
- Entity IDs are a public contract (`sensor.ncsender_*`, etc.) — users' automations depend on them.
  Renaming is a major bump.
- All control-path failures must surface as `NcSenderError` (frenck's review note, fixed in v0.3.2);
  buttons/services convert it to `HomeAssistantError`.
- Version in `manifest.json` == git tag == release title (`vX.Y.Z`, plain). Changelog entry per release.
- HA may not load `__init__.py` in the sandbox (3.12 syntax); import `const`/`client` by path for tests.

## Release routine (the PR→merge part is automatable; the release button is the owner's)
1. Branch → change → `manifest.json` bump → `CHANGELOG.md` entry → commit → push → open PR.
2. Validate workflow (hacs + hassfest) must be green. Workflows for first-time contributors need
   owner approval on the PR page before they run.
3. Squash-merge. **Then** publish a GitHub release (not just a tag) — HACS only sees releases.
   The permission guard blocks Claude from creating releases; the owner clicks that button.
4. HACS: users see the update; the owner's instance may need HACS → ncSender → ⋮ → Redownload.

## Upstream items to raise with Francis (ncSender)
- `job_status: error` on successful completion (Pro).
- `isToolChanging` not set for ATC swaps (Pro).
- Plugin sandbox has no network API; `Permissions` manifest field is parsed but unused. See
  `docs/ROADMAP.md` → "HA Switches plugin" for the comment-G-code design that works without it.
