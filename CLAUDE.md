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
- The **HA Switches** ncSender plugin lives in its own repo, `stmoha/ncsender-plugin-ha-switches`
  (moved out of `ncsender-plugin/` here at 0.1.9, history kept; local clone
  `C:/Users/stefa/Documents/GitHub/ncsender-plugin-ha-switches`). Its integration side here is
  `ha_switching.py` (allowlist, webhook, comment handler) + `parse_ha_command` in `client.py`.
  Registry PR waits for the stable v0.5.0 release (entry ready in that repo's `registry-entry.json`).
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
- **Two Pro quirks that are now FIXED — don't re-document them as current.** Observed Oct 2026 on
  Pro ~2.0.114; gone by the Pro build running mid-Nov 2026 (verified from the owner's HA recorder
  history, 2026-11-15: jobs end `running → completed`; `sender_status` shows `tool-changing` on every
  M6, including mid-job). Keep the fallbacks, drop the claims:
  - *Was:* `job_status: error` on a successful completion, progress stalled ~95%. *Now:* `completed`
    is reliable; `error` means a real error (the Nov 15 one went `tool-changing → hold → alarm`).
    The owner's `binary_sensor.cnc_job_finished` helper (`current_line >= total_lines - 5`, status not
    running/paused) still works and is a fine belt-and-suspenders for older Pro builds.
  - *Was:* `isToolChanging` not set for ATC swaps. *Now:* `sender_status` → `tool-changing` is emitted
    (confirmed Pro + community source, `CommandProcessor` step 12). `sensor.ncsender_tool_change`
    (timestamp, v0.3.1, fires on every acknowledged **M6**) remains useful because it fires *before*
    the swap and carries the tool/pocket; trigger on its state change with
    `not_from: [unknown, unavailable]`.
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

## Owner's Home Assistant (so YAML handed over is paste-ready — no `YOUR_*` placeholders for the owner)
- Phone notify target: `notify.mobile_app_iphone_24` (iOS, companion-app beta with Live Activities).
- Switches: chiller `switch.s4_cnc_chiller`, air assist `switch.garage_cnc_air`,
  dust collector `switch.garage_dust_collector_shelly_1_gen4`.
- Live Activity tag is `cnc_job` (script `script.cnc_live_activity_update`); the Clear automation ends
  it with `message: clear_notification` + that tag. Tags must match or the island never ends.
- Helper `binary_sensor.cnc_job_finished` (UI template helper) = `is_state(job_status, 'completed')`.
- HA has the Studio Code Server and Terminal add-ons. Config lives in `/config/automations.yaml` and
  `/config/scripts.yaml`; after overwriting a file by hand the owner must **Developer tools → YAML →
  Reload Automations / Scripts** — HA doesn't watch the files. UI-created helpers live in `.storage`,
  not in those files. Review the live config by having the owner download those two files.
- The owner's live automations are mirrored (with placeholders) in `examples/automations/`; keep both
  in step. The public copy uses `YOUR_*`; the owner's copy never should (lesson from 2026-11-17: a
  `notify.mobile_app_YOUR_PHONE` left in three automations silently sent nothing).

## Release routine (the PR→merge part is automatable; the release button is the owner's)
1. Branch → change → `manifest.json` bump → `CHANGELOG.md` entry → commit → push → open PR.
2. Validate workflow (hacs + hassfest) must be green. Workflows for first-time contributors need
   owner approval on the PR page before they run.
3. Squash-merge. **Then** publish a GitHub release (not just a tag) — HACS only sees releases.
   The permission guard blocks Claude from creating releases; the owner clicks that button.
4. HACS: users see the update; the owner's instance may need HACS → ncSender → ⋮ → Redownload.

## Upstream items to raise with Francis (ncSender)
- ~~`job_status: error` on successful completion (Pro)~~ — fixed upstream by Nov 2026.
- ~~`isToolChanging` not set for ATC swaps (Pro)~~ — fixed upstream by Nov 2026.
- Plugin sandbox has no network API; `Permissions` manifest field is parsed but unused. See
  `docs/ROADMAP.md` → "HA Switches plugin" for the comment-G-code design that works without it.
