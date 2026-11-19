# ncSender — Home Assistant integration

[![Validate](https://github.com/stmoha/ha-ncsender/actions/workflows/validate.yml/badge.svg)](https://github.com/stmoha/ha-ncsender/actions/workflows/validate.yml)

Native Home Assistant integration for [ncSender](https://github.com/siganberg/ncSender)
(community and Pro). Connects directly to ncSender's WebSocket — no MQTT broker,
no bridge service on the Pi, no changes to ncSender.

## Entities

Device **ncSender** with:

| Entity | Notes |
|---|---|
| `sensor.ncsender_machine_state` | Idle / Run / Hold / Alarm / Jog / Home / Door… Attributes: MPos/WPos, workspace, tool, overrides, pins |
| `sensor.ncsender_sender_status` | ncSender's own status |
| `sensor.ncsender_active_output` | `spindle` / `laser` / `off` |
| `sensor.ncsender_job_status` | none / loaded / running / paused / completed / stopped / error. Attributes: line counts, runtime, start/end |
| `sensor.ncsender_job_file`, `_job_progress`, `_job_time_remaining` | |
| `sensor.ncsender_spindle_rpm`, `_feed_rate`, `_laser_power` | telemetry, throttled to 1/s |
| `sensor.ncsender_last_error` | latest cnc-error |
| `binary_sensor.ncsender_controller_connected` | SLB link up |
| `binary_sensor.ncsender_spindle` | VFD spindle running (stays on during coast-down) |
| `binary_sensor.ncsender_laser` | laser firing |
| `binary_sensor.ncsender_flood_coolant` / `_mist_coolant` | M8 / M7 state, tracked from acknowledged commands as well as status reports |
| `sensor.ncsender_machine_x/y/z` (+ `_a` etc. when present) | machine coordinates, mm (distance device class — switch any of these to inches in the entity settings) |
| `sensor.ncsender_work_x/y/z` (+ extra axes) | work coordinates in the active workspace |
| `sensor.ncsender_workspace` | active WCS (G54…G59). Attributes: every workspace's offsets per axis |
| `sensor.ncsender_current_tool` | tool/slot number the controller reports. Attributes: name, tool_id, pocket, type, diameter, TLO, life remaining, tool_length_set, tool_changing, and a `pockets` map of every assigned pocket → tool name |
| `sensor.ncsender_tool_change` | timestamp of the last acknowledged M6 — trigger on *any state change* for tool-change alerts. Attributes: `requested_tool`, `previous_tool`, `command` |
| `button.ncsender_pause_job`, `_resume_job`, `_stop_job` | job control |
| `switch.ncsender_output_pN` | grblHAL aux outputs (M64/M65), one per pin listed in options; bidirectional with ncSender's Auxiliary I/O buttons |

Service **`ncsender.send_command`** — send any G-code or realtime command:

```yaml
action: ncsender.send_command
data:
  command: "M8"
```

All entities go `unavailable` when the WebSocket drops; the integration reconnects with backoff.

## Install

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stmoha&repository=ha-ncsender&category=integration)

1. Click the button above (or in HACS: ⋮ → *Custom repositories* → add
   `https://github.com/stmoha/ha-ncsender`, type *Integration*), then **Download**.
2. Restart Home Assistant.
3. Add the integration:

   [![Open your Home Assistant instance and start setting up ncSender.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ncsender)

   Enter the host/IP of the machine running ncSender and port `8090`.

**Manual alternative:** copy `custom_components/ncsender/` into `/config/custom_components/` and restart.

## Example blueprints

Ready-made automations for common shop setups. Click **Import**, then create an automation
from the blueprint (Settings → Automations & scenes → Blueprints) and pick your devices:
no YAML or digging through triggers needed.

| Blueprint | What it does | |
|---|---|---|
| **Shop equipment follows the job** | Dust collector, shop vac, compressor, air assist… turn on while a job runs (optionally only once the spindle or laser is on) and off a few seconds after it ends; turns off after a long pause | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fstmoha%2Fha-ncsender%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fncsender%2Fequipment_follows_job.yaml) |
| **Job alerts** | Phone notifications: job finished/stopped/error with run time, tool change that hasn't finished after a minute (quick ATC swaps stay quiet), alarm or controller disconnect | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fstmoha%2Fha-ncsender%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fncsender%2Fjob_alerts.yaml) |
| **WLED status strip** | LED strip with ncSender status colors and a job progress bar | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fstmoha%2Fha-ncsender%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fncsender%2Fwled_status_strip.yaml) |
| **WLED equipment indicator** | A few LEDs on the same strip per device (dim = powered, bright = running with a power sensor) | [![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fstmoha%2Fha-ncsender%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fncsender%2Fwled_equipment_indicator.yaml) |

The WLED blueprints need a short `rest_command` snippet and some hardware: see
[examples/wled-status-strip.md](examples/wled-status-strip.md) for parts (about $25,
USB-powered), wiring and setup.

The blueprints default to the standard entity IDs (`sensor.ncsender_job_status`…); if you
renamed the ncSender device, pick your entities under **ncSender entities**.

## Icon

Brand images ship inside the integration (`custom_components/ncsender/brand/`, HA 2026.3+):
transparent logo for light theme, white-tile variant for dark theme. The logo belongs to
ncSender's author.

## Options

Settings → Devices & services → ncSender → **Configure**:

- **Laser S-value maximum** (default 1000) — see below.
- **Telemetry update interval** (default 5 s, range 1–60) — how often positions, RPM, feed rate,
  progress and time remaining update. State changes (job status, spindle/laser/coolant, alarms,
  tool, workspace) are always immediate regardless of this setting.
- **Aux output pins exposed as switches** — see below.
- **Devices ncSender may switch** — entities that `(HA <entity_id> ON|OFF|TOGGLE)` commands from
  ncSender may control. Empty by default: nothing is switched until you pick something.

## Controlling Home Assistant devices from ncSender's screen

### HA Switches plugin (v0.5.0+, prototype)

Install the **HA Switches** ncSender plugin from [`ncsender-plugin/`](ncsender-plugin/README.md),
add your devices (`Chiller, switch.chiller`, one per line), and allow the same entities in
Configure → *Devices ncSender may switch*. No automation, no aux pin, and no limit on how many.

- **Direct (recommended):** copy the webhook URL shown at the top of Configure into the plugin's
  *Home Assistant webhook URL*. Buttons then talk to HA directly and show each device's live state;
  they work with the controller off, before homing, and while a job is paused. The webhook only
  accepts requests from your local network and only switches the allowed devices.
- **Through the controller:** without a webhook URL each button sends a comment line such as
  `(HA switch.chiller ON)`; the controller ignores it and the integration switches the device once
  it's acknowledged. Needs the controller connected and no job paused. The same comment works
  inside a G-code file.

### Aux output pins

Each pin listed in options becomes `switch.ncsender_output_pN`, in step with ncSender's own
Auxiliary I/O switch for that output. Only the board's **real, unclaimed** aux outputs work: grblHAL
refuses higher numbers with `error:39` (on the SLB-EXT that leaves a few single-digit pins), so there
are no free "virtual" pins. To switch HA devices without using a pin, use the HA Switches plugin above.

1. **ncSender** → Settings → Advanced → Auxiliary I/O → *Add Output*: name it (e.g. "Shop Lights"),
   pick a free output on your board such as `M64 P2`. You now have a button on the main screen.
2. **Home Assistant** → ncSender → Configure → *Aux output pins exposed as switches*: `2`. After the
   reload, `switch.ncsender_output_p2` appears and follows that button.
3. Mirror it onto the real device with one automation:

```yaml
alias: Shop lights follow ncSender P2
mode: restart
triggers:
  - trigger: state
    entity_id: switch.ncsender_output_p2
    to: ["on", "off"]
actions:
  - action: "switch.turn_{{ trigger.to_state.state }}"
    target:
      entity_id: switch.shop_lights
```

The link is bidirectional: toggling `switch.ncsender_output_p2` in HA sends the M-code, and ncSender's
button lights up. `M64 P2` inside a G-code file works the same way.

## Database / recorder

Defaults are tuned so a long job doesn't bloat the Home Assistant database: telemetry is paced
(5 s) and quantized (RPM/feed to 10, positions to 0.01 mm, progress to 0.5 %). At those defaults an
8-hour job writes on the order of tens of thousands of rows, not hundreds of thousands.

If you never want telemetry history at all (live values only), you can additionally exclude it —
this is optional:

```yaml
recorder:
  exclude:
    entity_globs:
      - sensor.ncsender_machine_*
      - sensor.ncsender_work_*
      - sensor.ncsender_spindle_rpm
      - sensor.ncsender_feed_rate
      - sensor.ncsender_job_progress
      - sensor.ncsender_job_time_remaining
```

### Laser threshold

*Laser S-value maximum* (default 1000): spindle commands at or below this value with no
RPM feedback are classified as the laser; anything above is the VFD spindle.

## Notes on protocol

Built against ncSender's WebSocket stream as of Sep 2026 (`{"type","data"}` envelope;
full state on connect, shallow deltas after). ncSender has no API auth — anyone on the
LAN can read state and send commands, integration or not.
