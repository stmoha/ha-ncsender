# Changelog

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
