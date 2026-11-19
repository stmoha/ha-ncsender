# HA Switches — ncSender plugin (prototype)

Switch Home Assistant devices from ncSender's screen: chiller, air assist, dust collector, lights,
even the controller's own power. Each device gets On/Off buttons and, once connected directly, its
live on/off state.

Two ways to reach Home Assistant:

- **Direct (recommended, integration v0.5.0b2+).** The plugin posts to a local-only webhook that the
  **ha-ncsender** integration registers. Works with the controller off, before homing, in an alarm
  and while a job is paused, so it can switch on the controller itself.
- **Through the controller (fallback).** With no webhook URL set, each button sends a comment line
  such as `(HA switch.shop_lights ON)`. grblHAL ignores it and answers `ok`, and the integration
  switches the device once it sees the line acknowledged. Needs the controller connected and no job
  paused. The same comment works inside a G-code file.

Either way, only devices you allowed in the integration's Configure screen respond, so a G-code
file you downloaded can't switch your other devices.

## Setup

1. **Home Assistant** → Settings → Devices & services → ncSender → **Configure**.
   - Under *Devices ncSender may switch*, pick the entities and Submit.
   - Copy the **webhook URL** shown at the top of the same dialog.
2. **ncSender** → Settings → Plugins → *Install Plugin* → choose the ZIP
   (`com.cncdocs.ha-switches_<version>.zip`, built with `python ncsender-plugin/package.py`).
   Press Ctrl+F5 if the Plugins tab doesn't show **HA Switches** yet.
3. Open **HA Switches** → *Edit switches*:
   - Paste the webhook URL into *Home Assistant webhook URL*. *Find it in Home Assistant ↗* opens
     the integration page.
   - List the switches, one per line, then **Save**:

   ```
   Chiller, switch.s4_cnc_chiller
   Air, switch.garage_cnc_air
   Dust collector, switch.garage_dust_collector_shelly_1_gen4
   ```

4. Press **On** / **Off**. With the webhook set, each card shows the device's state.

**Hold to press.** Add `, hold` to a line (e.g. `Controller power, switch.slb_ext, hold`) and
both its buttons need a 1-second press, with a fill bar showing progress, like ncSender's own
*Hold* outputs. Use it for anything that shouldn't switch on a stray click.

**Opening it with the controller off.** ncSender greys out its Plugins tab unless it is Idle. Open
the same window from **Settings → Plugins → HA Switches → Settings**.

**Keyboard shortcuts.** *Keyboard shortcuts…* opens ncSender's Settings → Controls, where *HA
Switches* can be bound to a key to open this window. Shortcuts that toggle a single device need
ncSender's Auxiliary I/O outputs to support Home Assistant (drafted upstream; see `docs/ROADMAP.md`).

## Limits (prototype)

- The webhook URL is stored in the plugin's settings, which anyone who can reach ncSender on your
  network can read (ncSender has no login). The webhook only accepts local-network requests and only
  switches the devices you allowed, which is the same reach ncSender's own buttons give them anyway.
- The fallback route doesn't work while paused or with the controller off (see above).

## Debugging

Every command the integration sees fires an `ncsender_ha_command` event
(`entity_id`, `service`, `allowed`, `source` = `webhook` or `command`). Developer tools → Events →
listen to `ncsender_ha_command`, then press a button. `allowed: false` means the entity isn't in
Configure. "Can't reach Home Assistant" means the webhook URL is wrong or the integration is older
than v0.5.0b2.
