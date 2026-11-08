"""Example blueprints: load each one, build automations from them and drive them with fake states."""
from contextlib import ExitStack
from datetime import timedelta
from unittest.mock import patch
from pathlib import Path
import shutil

import pytest
from homeassistant.components.blueprint import models
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed

BLUEPRINTS = Path(__file__).parent.parent / "blueprints" / "automation" / "ncsender"

JOB, SPINDLE, LASER = "sensor.ncsender_job_status", "binary_sensor.ncsender_spindle", "binary_sensor.ncsender_laser"
MS, PROG, TOOL, CONN = ("sensor.ncsender_machine_state", "sensor.ncsender_job_progress",
                        "sensor.ncsender_current_tool", "binary_sensor.ncsender_controller_connected")


@pytest.fixture
async def bp(hass: HomeAssistant):
    dest = Path(hass.config.path("blueprints/automation/ncsender"))
    dest.mkdir(parents=True, exist_ok=True)
    for f in BLUEPRINTS.glob("*.yaml"):
        shutil.copy(f, dest / f.name)
    return lambda name: {"use_blueprint": {"path": f"ncsender/{name}.yaml", "input": {}}}


@pytest.fixture
def wled_calls(hass: HomeAssistant):
    calls: list[dict] = []

    async def handler(call: ServiceCall) -> None:
        calls.append(dict(call.data))

    hass.services.async_register("rest_command", "ncsender_wled", handler)
    return calls


async def _setup(hass, automations):
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "automation", {"automation": automations})
    await hass.async_block_till_done()


async def _set(hass, entity_id, state, attrs=None):
    hass.states.async_set(entity_id, state, attrs or {})
    await hass.async_block_till_done()


def test_blueprints_parse():
    from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
    from homeassistant.util.yaml import load_yaml_dict

    names = sorted(f.stem for f in BLUEPRINTS.glob("*.yaml"))
    assert names == ["equipment_follows_job", "job_alerts", "wled_equipment_indicator", "wled_status_strip"]
    for f in BLUEPRINTS.glob("*.yaml"):
        blueprint = models.Blueprint(load_yaml_dict(f), expected_domain="automation", schema=BLUEPRINT_SCHEMA)
        assert blueprint.metadata["source_url"].endswith(f.name)


async def test_job_alerts(hass, bp):
    from homeassistant.helpers import device_registry as dr
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    if not await async_setup_component(hass, "mobile_app", {}):
        pytest.skip("mobile_app's dependencies aren't installed in this test environment")
    phone_entry = MockConfigEntry(domain="mobile_app", data={"webhook_id": "abc", "device_id": "phone",
                                                             "device_name": "Phone"})
    phone_entry.add_to_hass(hass)
    phone = dr.async_get(hass).async_get_or_create(config_entry_id=phone_entry.entry_id,
                                                   identifiers={("mobile_app", "phone")}, name="Phone")
    sent: list[dict] = []

    async def notify(call: ServiceCall) -> None:
        sent.append(dict(call.data))

    hass.services.async_register("notify", "mobile_app_phone", notify)
    await _set(hass, JOB, "running"); await _set(hass, "sensor.ncsender_job_file", "sign.nc")
    await _set(hass, MS, "Run"); await _set(hass, "sensor.ncsender_last_error", "none")
    await _set(hass, "sensor.ncsender_tool_change", "2026-01-01T00:00:00+00:00",
               {"requested_tool": 3, "previous_tool": 1})
    await _set(hass, CONN, "on")
    cfg = bp("job_alerts")
    cfg["use_blueprint"]["input"] = {"notify_device": phone.id}
    await _setup(hass, [cfg | {"id": "alerts", "alias": "alerts"}])
    assert hass.states.get("automation.alerts").state == "on"   # config validated

    # Route the Companion app device action to our fake notify service.
    da = "homeassistant.components.mobile_app.device_action"
    stack = ExitStack()
    stack.enter_context(patch(f"{da}.webhook_id_from_device_id", return_value="abc"))
    stack.enter_context(patch(f"{da}.get_notify_service", return_value="mobile_app_phone"))
    await _set(hass, JOB, "completed", {"runtime_sec": 300})
    assert sent[-1]["title"] == "CNC job completed" and sent[-1]["message"] == "sign.nc – 5.0 min"
    await _set(hass, "sensor.ncsender_tool_change", "2026-01-01T00:05:00+00:00",
               {"requested_tool": 4, "previous_tool": 3})
    assert sent[-1]["message"] == "Load T4 (was T3)"
    await _set(hass, MS, "Alarm")
    assert sent[-1]["title"] == "CNC needs attention" and sent[-1]["message"] == "Machine in Alarm."
    stack.close()


async def test_equipment_follows_job(hass, bp, freezer):
    for e in ("input_boolean",):
        assert await async_setup_component(hass, e, {"input_boolean": {"dust": {}, "air": {}}})
    await _set(hass, JOB, "loaded"); await _set(hass, SPINDLE, "off"); await _set(hass, LASER, "off")
    cfg = bp("equipment_follows_job")
    cfg["use_blueprint"]["input"] = {"equipment": ["input_boolean.dust", "input_boolean.air"], "off_delay": 15,
                                     "pause_timeout": 10}
    await _setup(hass, [cfg | {"id": "eq", "alias": "eq"}])
    dust = lambda: hass.states.get("input_boolean.dust").state

    await _set(hass, JOB, "running")
    assert dust() == "off"                      # job running, spindle not yet on
    await _set(hass, SPINDLE, "on")
    assert dust() == "on" and hass.states.get("input_boolean.air").state == "on"

    await _set(hass, JOB, "paused")
    freezer.tick(timedelta(minutes=5)); async_fire_time_changed(hass); await hass.async_block_till_done()
    assert dust() == "on"
    freezer.tick(timedelta(minutes=6)); async_fire_time_changed(hass); await hass.async_block_till_done()
    assert dust() == "off"                      # paused too long

    await _set(hass, JOB, "running")
    assert dust() == "on"                       # resumed with spindle still on
    await _set(hass, SPINDLE, "off"); await _set(hass, JOB, "completed")
    freezer.tick(timedelta(seconds=10)); async_fire_time_changed(hass); await hass.async_block_till_done()
    assert dust() == "on"
    freezer.tick(timedelta(seconds=6)); async_fire_time_changed(hass); await hass.async_block_till_done()
    assert dust() == "off"                      # off_delay after completion

    await _set(hass, LASER, "on"); await _set(hass, JOB, "running")
    assert dust() == "on"                       # laser counts too


async def test_equipment_without_cutting_requirement(hass, bp):
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": {"vac": {}}})
    await _set(hass, JOB, "loaded"); await _set(hass, SPINDLE, "off"); await _set(hass, LASER, "off")
    cfg = bp("equipment_follows_job")
    cfg["use_blueprint"]["input"] = {"equipment": ["input_boolean.vac"], "require_cutting": False}
    await _setup(hass, [cfg | {"id": "eq", "alias": "eq"}])
    await _set(hass, JOB, "running")
    assert hass.states.get("input_boolean.vac").state == "on"


def _seg(call):
    return call["payload"]["seg"][0]


async def test_wled_status_strip(hass, bp, wled_calls, freezer):
    await _set(hass, MS, "Idle"); await _set(hass, JOB, "none"); await _set(hass, PROG, "0")
    await _set(hass, TOOL, "1", {"tool_changing": False}); await _set(hass, CONN, "on")
    await _set(hass, "light.wled", "on")
    cfg = bp("wled_status_strip")
    cfg["use_blueprint"]["input"] = {"wled_light": "light.wled", "wled_host": "10.0.0.5", "status_leds": 48,
                                     "progress_dim_pct": 7, "idle_timeout": 600, "fireworks_secs": 30}
    await _setup(hass, [cfg | {"id": "strip", "alias": "strip"}])

    await _set(hass, PROG, "40.0"); await _set(hass, JOB, "running")
    s = _seg(wled_calls[-1])
    assert wled_calls[-1]["host"] == "10.0.0.5"
    assert (s["start"], s["stop"], s["fx"], s["ix"], s["on"]) == (0, 48, 98, 40, True)
    assert s["col"][0] == [0, 255, 0] and s["col"][1] == [0, round(255 * 0.07 ** (1 / 2.8)), 0]

    await _set(hass, MS, "Hold:0")
    s = _seg(wled_calls[-1]); assert s["fx"] == 98 and s["col"][0] == [255, 193, 7]   # amber progress bar
    await _set(hass, TOOL, "1", {"tool_changing": True})
    assert _seg(wled_calls[-1])["col"][0] == [201, 18, 168]
    await _set(hass, TOOL, "1", {"tool_changing": False})
    await _set(hass, MS, "Alarm")
    assert _seg(wled_calls[-1])["col"][0] == [255, 0, 0]

    await _set(hass, MS, "Idle"); await _set(hass, JOB, "completed")
    s = _seg(wled_calls[-1]); assert s["fx"] == 42                                   # fireworks
    freezer.tick(timedelta(seconds=31)); async_fire_time_changed(hass); await hass.async_block_till_done()
    s = _seg(wled_calls[-1]); assert (s["fx"], s["col"][0], s["bri"], s["on"]) == (0, [255, 255, 255], 110, True)

    freezer.tick(timedelta(seconds=600)); async_fire_time_changed(hass); await hass.async_block_till_done()
    assert _seg(wled_calls[-1])["on"] is False                                       # idle timeout

    await _set(hass, CONN, "off")
    s = _seg(wled_calls[-1]); assert s["on"] is True and s["col"][0] == [255, 0, 0]  # disconnected = alarm


async def test_wled_no_fireworks_after_reload(hass, bp, wled_calls):
    await _set(hass, MS, "Idle"); await _set(hass, JOB, "unavailable"); await _set(hass, PROG, "100")
    await _set(hass, TOOL, "1", {"tool_changing": False}); await _set(hass, CONN, "on")
    await _set(hass, "light.wled", "on")
    cfg = bp("wled_status_strip")
    cfg["use_blueprint"]["input"] = {"wled_light": "light.wled", "wled_host": "10.0.0.5"}
    await _setup(hass, [cfg | {"id": "strip", "alias": "strip"}])
    await _set(hass, JOB, "completed")          # integration reload, not a finished job
    assert _seg(wled_calls[-1])["fx"] == 0


async def test_wled_equipment_indicator(hass, bp, wled_calls):
    await _set(hass, "light.wled", "on")
    await _set(hass, "switch.compressor", "off"); await _set(hass, "sensor.compressor_power", "0",
                                                             {"device_class": "power", "unit_of_measurement": "W"})
    await _set(hass, "switch.dust", "off")
    comp = bp("wled_equipment_indicator")
    comp["use_blueprint"]["input"] = {"device": "switch.compressor", "power_sensor": "sensor.compressor_power",
                                      "wled_light": "light.wled", "wled_host": "10.0.0.5", "segment": 2,
                                      "first_led": 53}
    dust = bp("wled_equipment_indicator")
    dust["use_blueprint"]["input"] = {"device": "switch.dust", "wled_light": "light.wled", "wled_host": "10.0.0.5",
                                      "segment": 1, "first_led": 49}
    await _setup(hass, [comp | {"id": "comp", "alias": "comp"}, dust | {"id": "dust", "alias": "dust"}])

    await _set(hass, "switch.compressor", "on")
    s = _seg(wled_calls[-1]); assert (s["id"], s["start"], s["stop"], s["on"], s["bri"]) == (2, 53, 56, True, 40)
    await _set(hass, "sensor.compressor_power", "1500", {"device_class": "power", "unit_of_measurement": "W"})
    assert _seg(wled_calls[-1])["bri"] == 255
    await _set(hass, "switch.dust", "on")
    s = _seg(wled_calls[-1]); assert (s["id"], s["start"], s["stop"], s["on"], s["bri"]) == (1, 49, 52, True, 255)
    assert s["col"] == [[255, 200, 150]]
