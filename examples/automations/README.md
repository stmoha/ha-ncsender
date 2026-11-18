# Example automations (owner's working set)

Plain HA automations the integration author runs on an AltMill / SLB-EXT with ncSender Pro.
For reusable, parameterised versions see the community blueprints in `../../blueprints/`.

| File | What's in it |
|---|---|
| `cnc_automations.yaml` | Chiller follows spindle · Air assist follows laser · Dust collector follows M8 · Job complete (critical alert) · Job error (alert) · Job Live Activity · Clear Live Activity |
| `cnc_live_activity_script.yaml` | The script the Live Activity automation calls — builds the Dynamic Island payload from the sensors (phase, progress, countdown, tool number). |

**Optional helper** — a template binary sensor some dashboards use
(Settings → Helpers → Template → Binary sensor, name `cnc_job_finished`):

```jinja
{{ is_state('sensor.ncsender_job_status', 'completed') }}
```

Replace every `YOUR_*` placeholder before saving. Entities referenced:
`sensor.ncsender_job_status` (attrs `current_line`, `total_lines`, `runtime_sec`), `sensor.ncsender_job_file`,
`sensor.ncsender_job_progress`, `sensor.ncsender_job_time_remaining`, `sensor.ncsender_sender_status`,
`sensor.ncsender_machine_state`, `sensor.ncsender_last_error`, `sensor.ncsender_tool_change` (attr `requested_tool`),
`binary_sensor.ncsender_spindle`, `binary_sensor.ncsender_laser`, `binary_sensor.ncsender_flood_coolant`.
