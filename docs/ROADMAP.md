# Roadmap

Status as of 2026-11-17. Keep this current — it replaces chat history as the project's memory.

## In flight

- **PR #3 — Aux output switches (v0.4.0).** `switch.ncsender_output_pN` per pin listed in a new
  `output_pins` option; state from `machineState.outputPinsState`, bidirectional with ncSender's
  Auxiliary I/O buttons. Validate green. **Waiting on merge + release.**
- **PR #2 — Example blueprints (tmuka, community).** Four HA blueprints + tests, no integration code.
  Workflows need owner approval to run (first-time contributor). Review, approve CI, merge.
  Suggest merging *after* #3 so its README/CHANGELOG edits don't conflict with v0.4.0's.

## Next: "HA Switches" — HA-controlled buttons on ncSender's screen with zero HA-side setup

**Problem.** Aux-output switches (v0.4.0) are limited to the board's real unclaimed outputs (a few),
and mirroring each onto an HA device needs an automation or a label per switch — too much setup for
other users.

**Constraint.** The ncSender plugin sandbox has **no network access**; a plugin cannot talk to HA.
It *can* register Tool Menu buttons and call `pluginContext.sendCommand()`, which lands on the same
command stream the integration already parses.

**Design.**
1. *ncSender plugin* ("HA Switches"): config UI defines switches — name, icon, HA entity ID. Each is a
   Tool Menu button. Pressing sends a **comment-only G-code line**: `(HA switch.shop_lights ON)`.
   grblHAL treats `( ... )` as a no-op and answers `ok`. No pin, no firmware limit → unlimited switches.
2. *Integration* (v0.5.0): parse `(HA <entity_id> ON|OFF|TOGGLE)` on acknowledged commands and call
   `homeassistant.turn_on/off/toggle`. The plugin's config *is* the mapping — no automation, no label.
3. **Allowlist (decided: ship allowlisted).** Any G-code file could otherwise control arbitrary HA
   devices (`(HA lock.front_door OFF)` in a downloaded .nc). The integration acts only on entity IDs
   listed once in Configure. Keeps "no HA setup" to a single field; nothing a file can't reach otherwise.
4. *Reverse channel* (ncSender button reflecting HA's real state, e.g. lights flipped at the wall):
   needs plugin-readable inbound state from ncSender — **upstream request to Francis**. First cut is
   fire-and-forget; integration can expose a `binary_sensor.ncsender_ha_switch_*` mirror for dashboards.

**Order of work.** Integration half first (v0.5.0) — it's harmless until something sends the comment
format, and it's a modest extension of the M6/M8 parser in `client.py`. Then the plugin, in the
pattern of the owner's existing ncSender plugins (gcode-reference, probe-plus).

## Later / ideas
- Position-based immediate binary sensors (e.g. "Z above safe height") so automations needn't rely
  on paced telemetry.
- Start-job button — deliberately omitted so far (remote-starting a spindle from a dashboard is a
  safety line to cross on purpose). Revisit with a confirmation gate.
- Pocket→tool-name resolution for the M6 sensor under RapidChange slot mapping, if users report the
  alert showing a pocket number where they expected a tool name.

## Done
- v0.1.0 native integration (replaced Pi MQTT bridge) · v0.2.0 positions/workspaces/tool ·
  v0.2.1 bundled brand icons · v0.3.0 recorder-friendly telemetry · v0.3.1 M6 tool-change sensor ·
  v0.3.2 NcSenderError on connection failures (frenck review) · HACS default store (Oct 2026).
