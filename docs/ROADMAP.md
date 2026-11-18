# Roadmap

Status as of 2026-11-18. Keep this current — it replaces chat history as the project's memory.

## In flight

- **v0.5.0 "HA Switches"** — branch `feature/ha-switches`: integration half done and tested
  standalone; plugin prototype `ncsender-plugin/` v0.1.0. Waiting on the owner's machine test
  (procedure below), then PR → merge → release.

## Owner's HA config (tracked)
- `examples/automations/` — the seven CNC automations, the Live Activity script, and the helper
  template, with `YOUR_*` placeholders. The owner's live HA copy has real entity IDs
  (`notify.mobile_app_iphone_24`, chiller/air/dust-collector switches). When the live config changes,
  update the example to match; when the integration's entity contract changes, update both.

## "HA Switches" — HA-controlled buttons on ncSender's screen with zero HA-side setup

**Problem.** Aux-output switches (v0.4.0) are limited to the board's real unclaimed outputs (a few),
and mirroring each onto an HA device needs an automation or a label per switch — too much setup for
other users.

**Constraint.** The ncSender plugin *JS engine* (Jint on pro-v2) has **no network access**; a plugin's
server-side code cannot talk to HA. But a plugin's **dialog HTML runs in the ncSender page**, so it can
`fetch` ncSender's own REST API (`/api/send-command`, `/api/plugins/<id>/settings`) — the G-code
Explorer plugin already does. That is the path used: no JS engine code at all.

**Design (as built, 2026-11-18).**
1. *ncSender plugin* `com.cncdocs.ha-switches` (`ncsender-plugin/`): manifest + `config.html` only
   (plus a v1 `index.js` wrapper). Tools → **HA Switches** opens a dialog with On/Off buttons per
   switch; the list is edited in the same dialog (`Name, entity_id` per line) and saved to the
   plugin's settings. A button POSTs `/api/send-command` with `(HA switch.x ON)`. On/Off rather than
   Toggle because the plugin can't see state.
2. *Integration* (v0.5.0): `parse_ha_command` in `client.py` matches
   `(HA <entity_id> ON|OFF|TOGGLE)` (optional `N123` prefix) on `cnc-command-result` with
   `status: success`; listeners get `(entity_id, service)`. `__init__.py` fires
   `ncsender_ha_command` {entity_id, service, allowed} and, if allowlisted, calls
   `homeassistant.<service>`.
3. **Allowlist** — Configure → *Devices ncSender may switch* (entity selector: switch, light, fan,
   input_boolean, script). Empty by default.
4. *Reverse channel* — not built. See "Next" below.

**Verified against ncSender source** (community .NET, local checkout, Nov 2026):
- `CncController.SendCommandAsync` **upper-cases** non-realtime commands before sending; the result's
  `command` is upper-case, `displayCommand` keeps the original. The parser is case-insensitive and
  lower-cases the entity ID (HA IDs are always lower-case).
- Job lines go out as `N<line> <text>` with `sourceId: "job"` and are broadcast like any other
  ack, so `(HA ...)` inside a G-code file works too (subject to the allowlist).
- Results with `meta.silent` or `sourceId: "system"` are **not** broadcast — the plugin must not
  send silently.
- `/api/send-command` always returns 200; failures come back as `{status:"error", message}` or
  `{status:"skipped", reason}`. The dialog shows those.
- **Hold blocks it:** `CommandProcessor.CheckHoldStateSafety` cancels every non-realtime command
  while `status` starts with `Hold`, comments included → buttons don't work while a job is paused.
- Controller must be connected (`SendCommandAsync` throws otherwise).

**Tested here (2026-11-18).** `client.py` standalone against a fake aiohttp ncSender that mimics the
real ack path (upper-casing, N-prefixed job lines, silent commands not broadcast, error/pending
results): 15/15 checks pass — parser accept/reject cases, dispatch order, coolant tracking
unaffected, a raising listener doesn't drop the socket, removed listener stops. The plugin page
was driven in a browser against a mock ncSender with the real `NcSenderClient` attached: save
three switches → reload keeps them → Chiller On / Dust Off produced `turn_on
switch.s4_cnc_chiller` and `turn_off switch.garage_dust_collector_shelly_1_gen4`. A harness test
`test_ha_switch_commands` (allowlist, job line, error status, event) is in `tests/` but was not run
here: the HA harness imports `fcntl`/`resource`, so it only runs on Linux/macOS (or WSL).

**Owner's machine test (to do).**
1. Install the branch build: copy `custom_components/ncsender/` from `feature/ha-switches` over
   `/config/custom_components/ncsender/` (Studio Code Server), restart HA.
2. HA → ncSender → Configure → *Devices ncSender may switch*: `switch.s4_cnc_chiller`,
   `switch.garage_cnc_air`, `switch.garage_dust_collector_shelly_1_gen4`.
3. Developer tools → Events → listen to `ncsender_ha_command`.
4. ncSender → Settings → Plugins → Install Plugin →
   `ncsender-plugin/dist/com.cncdocs.ha-switches_v0.1.0-test1.zip` (rebuild with
   `python ncsender-plugin/package.py v0.1.0-test1`), Ctrl+F5.
5. Tools → HA Switches → Edit switches → paste
   `Chiller, switch.s4_cnc_chiller` / `Air, switch.garage_cnc_air` /
   `Dust collector, switch.garage_dust_collector_shelly_1_gen4` → Save.
6. Press each On/Off. Expect: console shows `(HA SWITCH.… ON)` with `ok`, an event with
   `allowed: true`, the device switches.
7. Edge checks, note results here: (a) a non-allowlisted entity → event `allowed: false`, warning
   in the HA log, nothing switches; (b) machine in **Alarm** — does grblHAL still `ok` a comment-only
   line? (c) during a **running job** — does the queued line go out promptly between job lines?
   (d) **paused job** — expected to be cancelled (see above); (e) a two-line test file
   `(HA switch.garage_cnc_air ON)` / `(HA switch.garage_cnc_air OFF)` run as a job; (f) the dialog
   looks right in the portrait kiosk.

**Next.**
- *Reverse channel without an upstream change:* the integration could GET-merge-PUT
  `/api/plugins/com.cncdocs.ha-switches/settings` with `{"states": {entity: on|off}}` when an
  allowlisted entity changes, and the open dialog polls GET every ~2 s to light the buttons.
  Caveats: PUT replaces the whole settings file (must merge, small race with a user Save), and the
  plugin id becomes a contract. Alternatively ask Francis for a generic plugin broadcast endpoint.
- *Upstream asks for Francis:* let comment-only lines through `CheckHoldStateSafety` (they never
  move the machine) so switches work while paused; optionally main-screen plugin buttons (today
  the dialog is one tap away in the Tools menu).
- Move the plugin to its own repo (`ncsender-plugin-ha-switches`) and list it in
  `siganberg/ncSender.plugins-registry` once the owner is happy with it.

## Later / ideas
- Position-based immediate binary sensors (e.g. "Z above safe height") so automations needn't rely
  on paced telemetry.
- Start-job button — deliberately omitted so far (remote-starting a spindle from a dashboard is a
  safety line to cross on purpose). Revisit with a confirmation gate.
- Pocket→tool-name resolution for the M6 sensor under RapidChange slot mapping, if users report the
  alert showing a pocket number where they expected a tool name.

## Done
- 2026-11-18: v0.4.1 released (blueprints).
- 2026-11-18: PR #2 example blueprints (tmuka) merged — four blueprints, WLED guide, tests;
  WLED strip redraws once per whole percent. PR #6 owner's automations in `examples/automations/`.
- 2026-11-17: owner's HA automations brought current for Pro (completion on `completed`, real `error`
  alert, Live Activity shows `tool-changing` + tool number). PR #5 docs correction merged.
- v0.1.0 native integration (replaced Pi MQTT bridge) · v0.2.0 positions/workspaces/tool ·
  v0.2.1 bundled brand icons · v0.3.0 recorder-friendly telemetry · v0.3.1 M6 tool-change sensor ·
  v0.3.2 NcSenderError on connection failures (frenck review) · HACS default store (Oct 2026) ·
  v0.4.0 aux output switches (PR #3, released 2026-11-17) · CLAUDE.md + this roadmap (PR #4).
