# HA Switches — ncSender plugin (prototype)

Switch Home Assistant devices from ncSender's screen: chiller, air assist, dust collector, lights.

ncSender plugins can't reach the network, so the plugin doesn't talk to Home Assistant. Each
button sends a comment line to the controller instead:

```
(HA switch.shop_lights ON)
```

grblHAL ignores comments and answers `ok`. ncSender broadcasts the acknowledged line, and the
**ha-ncsender** integration (v0.5.0+) turns it into `homeassistant.turn_on` / `turn_off` /
`toggle` for that entity.

## Setup

1. **Home Assistant** → Settings → Devices & services → ncSender → **Configure** →
   *Devices ncSender may switch*: pick the entities. Anything not listed is ignored, so a G-code
   file you downloaded can't switch your other devices.
2. **ncSender** → Settings → Plugins → *Install Plugin* → choose the ZIP
   (`com.cncdocs.ha-switches_<version>.zip`, built with `python ncsender-plugin/package.py`).
   Press Ctrl+F5 if the Tools menu doesn't show **HA Switches** yet.
3. Tools → **HA Switches** → *Edit switches*, one per line, then **Save**:

   ```
   Chiller, switch.s4_cnc_chiller
   Air, switch.garage_cnc_air
   Dust collector, switch.garage_dust_collector_shelly_1_gen4
   ```

4. Press **On** / **Off**. The ncSender console shows the comment line; the device switches.

The same comment works inside a G-code file, e.g. `(HA switch.garage_dust_collector_shelly_1_gen4 ON)`
at the start of a job. Toggle is supported (`TOGGLE`), but the plugin offers On/Off only, because it
can't see the device's current state.

## Limits (prototype)

- **Not while paused.** ncSender holds every non-realtime command while the machine is in Hold,
  so buttons do nothing during a paused job (the console shows the command as cancelled).
- **Controller must be connected.** ncSender sends the line to grblHAL; with no controller there's
  nothing to acknowledge it.
- **One-way.** Buttons don't show whether a device is on. See `docs/ROADMAP.md` for the reverse
  channel idea.
- No authentication: like everything in ncSender, anyone on the LAN who can reach ncSender can
  press these buttons. The integration's allowlist limits *which* devices they reach.

## Debugging

Every command the integration sees fires an `ncsender_ha_command` event
(`entity_id`, `service`, `allowed`). Developer tools → Events → listen to `ncsender_ha_command`, then
press a button. `allowed: false` means the entity isn't in Configure; no event means the line never
got acknowledged (check the ncSender console).
