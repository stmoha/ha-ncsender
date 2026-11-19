# Roadmap

Status as of 2026-11-18. Keep this current — it replaces chat history as the project's memory.

## In flight

- **v0.5.0 "HA Switches"** — branch `feature/ha-switches`: integration half done and tested
  standalone; webhook route in betas b2/b3. The plugin moved to its own repo
  [stmoha/ncsender-plugin-ha-switches](https://github.com/stmoha/ncsender-plugin-ha-switches) at
  0.1.9 (2026-11-19). Next: publish b3, owner tests, then PR → merge → **v0.5.0 release**, and
  only then the ncSender plugin-registry PR (siganberg/ncSender.plugins-registry, `plugins.json`;
  the entry is ready in the plugin repo's `registry-entry.json`, bump its `version` first).

## Owner's HA config (tracked)
- `examples/automations/` — the seven CNC automations, the Live Activity script, and the helper
  template, with `YOUR_*` placeholders. The owner's live HA copy has real entity IDs
  (`notify.mobile_app_iphone_24`, chiller/air/dust-collector switches). When the live config changes,
  update the example to match; when the integration's entity contract changes, update both.

## "HA Switches" — HA-controlled buttons on ncSender's screen with zero HA-side setup

**Problem.** Aux-output switches (v0.4.0) are limited to the board's real unclaimed outputs (a few),
and mirroring each onto an HA device needs an automation or a label per switch — too much setup for
other users.

**Constraint (when built; since lifted upstream, see "Plugin web requests" under Next steps).** The
ncSender plugin *JS engine* (Jint on pro-v2) had **no network access**; a plugin's server-side code
could not talk to HA. But a plugin's **dialog HTML runs in the ncSender page**, so it can
`fetch` ncSender's own REST API (`/api/send-command`, `/api/plugins/<id>/settings`) — the G-code
Explorer plugin already does. That is the path used: no JS engine code at all.

**Design (as built, 2026-11-18).**
1. *ncSender plugin* `com.cncdocs.ha-switches` (originally `ncsender-plugin/`, now its own repo): manifest + `config.html` only
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
- *Main-screen switches (the real goal) — needs a small upstream change.* Checked upstream
  siganberg/ncSender `main` (2026-11-17): Aux I/O outputs are now **providers** in
  `src/NcSender.Client/src/lib/aux-outputs.ts`: each saved output is its "on" command, and a provider
  maps it to the "off" command. Francis's own Wireless I/O provider already uses a comment sentinel,
  `(DONGLE:xio:out 2 1)`, the same pattern as ours. Today the Add Output dialog is a dropdown
  (M7/M8, `M64 P0..Pn-1`, Wireless I/O), so `(HA …)` can't be picked. Writing it into
  `settings.auxOutputs` by hand gives a main-screen switch whose **On** works but whose **Off**
  sends nothing (no provider knows the off command), and whose state is local-only. So no
  workaround; propose upstream:
  1. `aux-outputs.ts`: an HA provider, `(HA <entity_id> ON)` → `(HA <entity_id> OFF)` (~5 lines).
  2. `AuxOutputDialog.vue`: a "Home Assistant" output choice with an entity-ID field.
  3. `GCodeVisualizer.vue`: set the switch state from successful `cnc-command-result` lines
     `(HA <entity_id> ON|OFF)` (like the bridge's `dongle:device-message` listener), so job lines
     and other clients stay in sync.
  4. Reverse direction, integration-only: when an allowlisted entity changes in HA (not from our
     own call — track the Context), send `(HA <entity_id> ON|OFF)` to ncSender so the switch
     follows. The integration then sees the ack and calls turn_on on an already-on entity — a
     no-op, no loop.
  With that, the HA Switches plugin becomes optional (or just a helper that writes the outputs).
  **Drafted 2026-11-18** (not sent): branches `feature/home-assistant-aux-output` (parts 1-3) and
  `feature/aux-output-shortcuts` (a "Toggle <output>" keyboard/gamepad action for every Aux I/O output,
  so HA outputs get shortcuts too) in a worktree of the owner's ncSender clone,
  `GitHub/ncSender-ha-aux`. Client tests + `vite build` pass; not clicked through (server needs
  .NET 10). Part 4 (integration pushes HA-side changes back) is still to do, in this repo.
- *Plugin shortcuts today:* every manifest `toolMenu` item is bindable (`Plugin:<id>:<item>`), but on
  pro-v2 an item can only open the plugin's dialog, not run code. So a per-switch shortcut is possible
  only as a hack (one menu item per switch slot, dialog sends TOGGLE and closes itself). Upstream
  shortcuts for Aux I/O outputs are the clean route.
- *Plugin web requests (upstream, Nov 2026; read in community `main` @ 89473283,
  `Plugins/JsPluginEngine.Host.cs`):* server-side JS plugins now get, per manifest `permissions`:
  - `pluginContext.http.request({method,url,headers,body,timeoutMs}, cb)`: async, off the engine lock
    (needs `"network"`). No WebSocket, so it can poll but not subscribe.
  - `pluginContext.storage.get()/set()`: a private JSON file **not** served by the settings API
    (made for sign-in tokens). Ends the "token readable on the LAN" objection.
  - `pluginContext.setInterval`, `sendCommand`, `getServerState`, and `onRequest(payload)`, which the
    plugin's own window reaches with `POST /api/plugins/<id>/request`.
  - Permissions are granted from the manifest at load; no consent prompt was found in the client.

  **Built in v0.5.0b2 (simpler variant, no server-side plugin code):** the integration's webhook
  (part 1 below) exists, and the plugin's *page* posts to it directly from the browser (`text/plain`,
  so no CORS preflight; the reply carries `Access-Control-Allow-Origin: *`). Buttons work with the
  controller off or paused and show live states. Still open from the list below: catching `(HA …)`
  lines from G-code files and the main-screen switches, which needs the server-side `onBeforeCommand`
  hook (part 2).

  **What it unlocks — proposed "HA bridge" mode:**
  1. *Integration:* register an HA **webhook** (`webhook` dependency, `local_only`), show its URL in
     Configure. Body `{"entity_id","action"}` → same allowlist + `homeassistant.*` call as today;
     `{"action":"states"}` → states of the allowlisted entities. No HA token ever leaves HA; the
     webhook ID is the only secret and is limited to the allowlist.
  2. *Plugin:* add a commands file with `events: ["onBeforeCommand", "background"]`,
     `permissions: ["network"]`; keep the webhook URL in `storage`.
     - `onBeforeCommand` swallows `(HA …)` lines (returns `[]`) and POSTs them to the webhook.
       This runs in `PluginCommandProcessor` **before** `CheckHoldStateSafety` and before any
       controller send, so switches work **while paused and with no controller connected** — both
       current limits gone, no upstream Hold change needed. Same for the main-screen HA aux outputs
       (PR 1 drafts) and lines in a G-code file.
     - `setInterval` polls `states` (e.g. 2 s) so the dialog shows real on/off.
  3. Fallback: with no webhook configured, the plugin does nothing and lines go to the controller as
     today, so the comment path keeps working.

  **Open points before building:** whether a swallowed **job** line is processed at stream time
  (switch fires when the line is reached) or ahead of it; the client sees `status: "skipped"` for a
  swallowed line (the dialog currently shows that as an error; the plugin should answer via its window
  instead); whether the owner's **Pro** build has the same `http`/`storage` API (only the community
  source was read); PR 1's switch follows `cnc-command-result`, which a swallowed line never emits.
  The plugin would then need to drive that state, or the PR keeps both paths.
- *Upstream ask for Francis (moot if the HA bridge mode above is built):* let comment-only lines through `CheckHoldStateSafety` (they never
  move the machine) so switches work while paused.
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
