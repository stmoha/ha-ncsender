# Changelog

## 0.5.0 — unreleased (betas: v0.5.0b1–b3; pre-releases from `feature/ha-switches`)
- **Switch HA devices from ncSender.** The integration now acts on comment lines of the form
  `(HA <entity_id> ON|OFF|TOGGLE)` once the controller acknowledges them, calling
  `homeassistant.turn_on` / `turn_off` / `toggle`. Only entities picked in the new option
  *Devices ncSender may switch* (Configure; switches, lights, fans, input booleans, scripts) are
  acted on, so a downloaded G-code file can't reach anything else. Works from the new
  **HA Switches** ncSender plugin (prototype in `ncsender-plugin/`) and from comments inside a job.
- Every such command fires an `ncsender_ha_command` event (`entity_id`, `service`, `allowed`)
  for debugging and automations.
- **Corrected:** the *Aux output pins* help text and readme no longer claim unused pin numbers work
  as virtual switches. grblHAL refuses outputs the board doesn't have (`error:39`), so only real,
  unclaimed outputs work. Use *Devices ncSender may switch* for HA devices instead.
- Fixed "Translation error: UNCLOSED_TAG" under *Devices ncSender may switch* (the help text
  contained `<entity_id>`, which HA's translation parser reads as a tag).
- HA Switches plugin 0.1.1: pressing inside the dialog and releasing outside it no longer closes
  it; with unsaved edits a backdrop click doesn't close it either (× still does); unsaved edits are
  kept and restored when the dialog reopens; more padding; no overflow in narrow windows.
- **Direct switching webhook (b2).** The integration registers a local-only webhook; its URL is
  shown at the top of Configure. The HA Switches plugin posts to it directly, so its buttons work
  with the controller off, before homing, in an alarm and while a job is paused. Same allowlist; no
  HA token leaves Home Assistant. `{"action": "states"}` returns the allowed devices' states. The
  `ncsender_ha_command` event gains `source` (`command` or `webhook`).
- HA Switches plugin 0.1.2: *Home Assistant webhook URL* setting (with a link to the integration
  page where it's shown), live on/off state per device, *Open Home Assistant* link, *Keyboard
  shortcuts…* button that opens ncSender Settings → Controls, official Home Assistant icon.
- HA Switches plugin 0.1.3: *Keyboard shortcuts…* also types "HA Switches" into the Controls search,
  so only the plugin's row shows.
- HA Switches plugin 0.1.4: optional hold-to-press per switch (`Name, entity_id, hold`). Both
  buttons then need a 1-second press, like ncSender's own *Hold* outputs, for devices such as the
  controller's power that shouldn't switch on a stray click.
- Fixed (b3): the webhook dropped every browser request ("no connection" in the plugin). It set
  its own CORS header, which HA's CORS handling refuses; HA's webhook view already allows any origin.

## 0.4.1 — 2026-11-18
- Example automation blueprints in `blueprints/automation/ncsender/`, with one-click import
  buttons in the README: shop equipment follows the job (spindle/laser aware), job alerts,
  WLED status strip with progress bar, and WLED equipment indicators. Contributed by tmuka (PR #2).
- `examples/wled-status-strip.md`: parts, wiring and setup guide for a USB-powered WLED
  status strip.

## 0.4.0 — 2026-11-08
- **Aux output switches.** New option *Aux output pins exposed as switches* (Configure → e.g. `0, 2`).
  Each listed grblHAL aux output becomes `switch.ncsender_output_pN`, mirroring ncSender's own
  Auxiliary I/O state: a press in ncSender's UI, an `M64 Pn` in a job, or a toggle in Home Assistant
  all stay in sync. A pin needs no physical wiring — an unused number is a *virtual switch* you can
  mirror onto any HA device, giving you an HA-controlled button on ncSender's main screen.

## 0.3.2 — 2026-11-04
- Connection failures and timeouts on control requests (Pause/Resume/Stop buttons, `send_command`
  action) now surface as a clean Home Assistant error instead of a raw traceback. Thanks to
  @frenck for the review note during HACS default-store inclusion.

## 0.3.1 — 2026-10-01
- New `sensor.ncsender_tool_change` (timestamp): updates on every acknowledged **M6**, before the
  swap happens. Attributes: `requested_tool`, `previous_tool`, `command`. Trigger automations on
  this entity's state change for a reliable tool-change signal with ATC plugins, which may not
  update the sender's own tool-changing flag or report the new tool number via status reports.

## 0.3.0 — 2026-09-09
Recorder-friendly defaults — no configuration.yaml changes needed to keep the database small.
- Telemetry update interval is now a config option (Settings → ncSender → Configure), default **5 s**
  (was fixed 1 s). State changes — job status, spindle/laser/coolant, alarms, tool, workspace — are
  still pushed immediately; only positions, RPM, feed, progress and time-remaining are paced.
- Telemetry is quantized so jitter doesn't create history rows: RPM and feed to 10, positions to
  0.01 mm, progress to 0.5 %, time remaining to 10 s.
- Removed the duplicate position attributes from `sensor.ncsender_machine_state` (the dedicated
  position sensors carry them), so that entity no longer rewrites every second during a job.
- Position sensors no longer declare `state_class: measurement` (no long-term statistics of coordinates).

## 0.2.2 — 2026-09-09
- Repository metadata for HACS submission. No functional changes.

## 0.2.1 — 2026-09-09
- Brand icons bundled in `custom_components/ncsender/brand/` (HA 2026.3+ local brand images):
  transparent logo for light theme, white-tile variant for dark theme.

## 0.2.0 — 2026-09-09
- Position sensors: `sensor.ncsender_machine_x/y/z` and `sensor.ncsender_work_x/y/z` (mm, distance
  device class); extra axes (e.g. A) added automatically from ncSender's reported axis list.
- `sensor.ncsender_workspace`: active WCS with G54–G59 offsets per axis as attributes.
- `sensor.ncsender_current_tool`: controller tool/slot number with tool-library attributes
  (name, tool_id, pocket, type, diameter, TLO, life remaining, TLO-set, tool-changing) and a
  `pockets` map; library fetched on connect and refreshed on `tools-updated`.

## 0.1.0 — 2026-09-09
- Initial release. Native WebSocket client for ncSender (no MQTT, no bridge).
- 16 entities mirroring the former MQTT bridge with identical entity IDs; Pause/Resume/Stop
  buttons; `ncsender.send_command` service.
- Hardened state handling ported from the bridge: trailing-flush telemetry throttle, stale
  accessory-flag workarounds, spindle/laser discrimination, M7/M8/M9 command tracking.
