# Changelog

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
