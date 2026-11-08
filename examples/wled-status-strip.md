# WLED status strip for ncSender

A USB-powered LED strip that shows what the machine is doing, from across the shop:

- **Status colors** matching the official ncSender RGB LED plugin: red alarm, orange door,
  magenta tool change, amber hold, blue homing, green running/jogging, white idle.
- **Job progress bar** in the current status color: full brightness up to the progress %,
  dim above it (so a held job shows an amber bar at its progress).
- **Fireworks** for a few seconds when a job finishes, then idle white; the strip turns off
  after the machine has been idle for a while.
- Optional **equipment indicators** at the end of the strip: a few LEDs per device
  (dust collector, compressor, air assist…).

Everything runs in Home Assistant with two blueprints; WLED needs no presets or playlists.

## Parts (about $25)

| Part | Notes |
|---|---|
| WLED controller | Any ESP32 WLED controller works. Tested with the **GLEDOPTO GL-MC-001WL** (mini ESP32, USB-A power input, 3-pin JST output, ships with WLED). It passes 5 V straight through, max 3 A. |
| WS2812B strip, **5 V**, 60 LEDs/m | 1 m (60 LEDs) is plenty. Cut longer strips down: each LED draws about 1 mA even when dark. |
| USB-A wall charger, **5 V 2.4–3 A** | Not a laptop/PC port (0.5–0.9 A). USB chargers are fixed at 5 V, so there's no wrong-voltage risk. |

## Wiring

1. **Cut** the strip to length across the middle of the copper pads, keeping the piece with
   the **input connector** (the arrows on the strip point away from the input).
2. **Cap or tape** the loose red/white power pigtails at the input end; at 1 m they aren't needed.
3. **Connect** the controller's 3-pin JST to the strip's input JST (keyed: 5 V, data, GND).
4. **Power** the controller from the USB charger.

## WLED setup

1. Join the `WLED-AP` Wi-Fi network, open `4.3.2.1`, and connect WLED to your home Wi-Fi.
2. **Config → LED Preferences**:
   - LED type **WS281x**, color order **GRB**, LED count = your strip length.
   - **Automatic brightness limiter on**, set to about 80 % of the charger rating
     (2.4 A charger → 1900 mA, 3 A → 2400 mA). The limiter dims the strip instead of
     overloading the charger.
3. Optional: **Config → WiFi Setup**, leave ESP-NOW off; turn off UDP sync receive and
   audio-reactive mode if your firmware has them (not used here).
4. **Reserve the controller's IP** in your router (the blueprints talk to it by address).
5. Home Assistant discovers the WLED device automatically; accept it.

## Home Assistant setup

1. Add this to `configuration.yaml` and restart Home Assistant:

   ```yaml
   rest_command:
     ncsender_wled:
       url: "http://{{ host }}/json/state"
       method: POST
       content_type: application/json
       payload: "{{ payload | to_json }}"
   ```

2. **Faster progress (recommended):** Settings → Devices & services → ncSender → Configure →
   telemetry update interval **1 s** (default 5 s, which makes the bar jump on short jobs).
   To keep the database small at 1 s, exclude the position sensors from the recorder:

   ```yaml
   recorder:
     exclude:
       entity_globs:
         - sensor.ncsender_machine_?
         - sensor.ncsender_work_?
   ```

3. Import the **ncSender – WLED status strip** blueprint (see the main README) and create
   an automation from it: pick the WLED light, enter the controller's IP, and set
   **Status LEDs** (for example 48 of 60 if you want room for indicators).
4. Optional: import **ncSender – WLED equipment indicator** and create one automation per
   device. Example layout for a 60-LED strip:

   | LEDs | WLED segment | Shows |
   |---|---|---|
   | 0–47 | 0 | Status / progress bar (status blueprint, Status LEDs = 48) |
   | 48 | – | dark gap |
   | 49–51 | 1 | Dust collector (first LED 49, 3 LEDs) |
   | 52 | – | dark gap |
   | 53–55 | 2 | Compressor, with its power sensor: dim = powered, bright = motor running |
   | 56 | – | dark gap |
   | 57–59 | 3 | Air assist |

## Tuning

- **Progress bar dim part:** 5–15 % is a good range. The value is gamma-corrected for
  WLED's default gamma 2.8, so 50 % looks about half as bright as full.
- **Idle timeout:** seconds of unchanged Idle before the status LEDs turn off; any state
  change lights them again. 0 keeps them on.
- **Colors** are in the blueprint's `colors:` variable if you want different ones (take
  control of the automation in the editor to change them).

## Troubleshooting

- **Nothing lights:** check the IP in the automation, that the `rest_command` snippet is in
  `configuration.yaml` and HA was restarted, and the automation's trace for errors.
- **Red and green swapped:** the color order isn't GRB for your strip; try RGB in LED Preferences.
- **Dim or flickering at full green:** raise the brightness limiter to match the charger.
