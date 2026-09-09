"""Boot HA, run the config flow against a fake ncSender, verify entities and controls."""
import asyncio, json
import pytest
from aiohttp import web
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from custom_components.ncsender.const import DOMAIN

FULL = {'senderStatus':'idle','machineState':{'status':'Idle','connected':True,'spindleActive':False,
        'floodCoolant':False,'mistCoolant':False,'spindleRpmTarget':0,'spindleRpmActual':0,'feedRate':0,
        'MPos':'1,2,3,45','WPos':'0.5,0,0,45','homed':True,'workspace':'G54','tool':3,'axes':'XYZA',
        'g54':'-713.968,-840.164,51.774,7100.346','g55':'-1227.988,-1227.988,0,0','toolLengthSet':True},'jobLoaded':None}

@pytest.fixture
async def fake_ncsender(socket_enabled):
    state = {"cmds": [], "ws": None}
    async def ws_handler(request):
        ws = web.WebSocketResponse(); await ws.prepare(request); state["ws"] = ws
        await ws.send_str(json.dumps({"type":"server-state-updated","data":FULL}))
        async for _ in ws: pass
        return ws
    async def health(r): return web.json_response({"status":"ok"})
    async def cmd(r): state["cmds"].append(await r.json()); return web.json_response({})
    async def pause(r): state["cmds"].append("PAUSE"); return web.json_response({})
    async def tools(r): return web.json_response([
        {"id":1,"toolId":101,"toolNumber":1,"name":"1/4 Endmill","type":"flat","diameter":6.35,"offsets":{"tlo":-12.5}},
        {"id":2,"toolId":102,"toolNumber":3,"name":"1/8 Ballnose","type":"ball","diameter":3.175,"offsets":{"tlo":-9.1},"life":{"remainingMinutes":42}},
        {"id":3,"toolId":103,"toolNumber":None,"name":"Unassigned V-bit"}])
    app = web.Application()
    app.router.add_get('/', ws_handler); app.router.add_get('/api/health', health)
    app.router.add_get('/api/tools', tools); app.router.add_post('/api/send-command', cmd); app.router.add_post('/api/gcode-job/pause', pause)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 18091); await site.start()
    yield state
    await runner.cleanup()

async def test_full_flow(hass, fake_ncsender):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"],
        {"host": "127.0.0.1", "port": 18091, "name": "ncSender", "laser_max_s": 1000})
    assert result["type"] is FlowResultType.CREATE_ENTRY, result
    entry = result["result"]
    await hass.async_block_till_done()
    await asyncio.sleep(0.3)  # let the WS connect and full state land

    # entity IDs match the old MQTT bridge naming
    for eid, expected in [("sensor.ncsender_machine_state", "Idle"),
                          ("sensor.ncsender_job_status", "none"),
                          ("binary_sensor.ncsender_controller_connected", "on"),
                          ("binary_sensor.ncsender_spindle", "off"),
                          ("binary_sensor.ncsender_flood_coolant", "off"),
                          ("sensor.ncsender_active_output", "off")]:
        st = hass.states.get(eid); assert st is not None, f"{eid} missing: {[s.entity_id for s in hass.states.async_all()]}"
        assert st.state == expected, (eid, st.state)
    assert hass.states.get("sensor.ncsender_machine_state").attributes["mpos_x"] == 1.0
    # positions: static XYZ + dynamic A axis, mm with distance device class
    assert hass.states.get("sensor.ncsender_machine_x").state == "1.0"
    assert hass.states.get("sensor.ncsender_work_x").state == "0.5"
    a = hass.states.get("sensor.ncsender_machine_a"); assert a is not None and a.state == "45.0"
    assert hass.states.get("sensor.ncsender_machine_z").attributes["unit_of_measurement"] == "mm"
    # workspace with G54-G59 offsets
    ws_s = hass.states.get("sensor.ncsender_workspace"); assert ws_s.state == "G54"
    assert ws_s.attributes["g54"]["a"] == 7100.346 and "g55" in ws_s.attributes and "g56" not in ws_s.attributes
    # current tool resolved via pocket (toolNumber) with library + pocket map
    t = hass.states.get("sensor.ncsender_current_tool"); assert t.state == "3", t
    assert t.attributes["name"] == "1/8 Ballnose" and t.attributes["pocket"] == 3 and t.attributes["tool_id"] == 102
    assert t.attributes["pockets"] == {"1": "1/4 Endmill", "3": "1/8 Ballnose"}
    assert t.attributes["life_remaining_min"] == 42 and t.attributes["tool_length_set"] is True

    # push deltas: job running, M8, laser fire
    ws = fake_ncsender["ws"]
    async def send(t, d):
        await ws.send_str(json.dumps({"type":t,"data":d})); await asyncio.sleep(0.05); await hass.async_block_till_done()
    await send("server-state-updated", {'jobLoaded':{'filename':'sign.nc','status':'running','progressPercent':42.3,'remainingSec':321}})
    assert hass.states.get("sensor.ncsender_job_status").state == "running"
    assert hass.states.get("sensor.ncsender_job_file").state == "sign.nc"
    await send("server-state-updated", {'machineState':{'tool':1}})
    assert hass.states.get("sensor.ncsender_current_tool").attributes["name"] == "1/4 Endmill"
    await send("tools-updated", [{"id":1,"toolId":101,"toolNumber":1,"name":"Renamed Endmill"}])
    assert hass.states.get("sensor.ncsender_current_tool").attributes["name"] == "Renamed Endmill"
    await send("cnc-command-result", {"command":"M8","status":"success"})
    assert hass.states.get("binary_sensor.ncsender_flood_coolant").state == "on"
    await send("server-state-updated", {'machineState':{'spindleActive':True,'spindleRpmTarget':800,'spindleRpmActual':0}})
    assert hass.states.get("binary_sensor.ncsender_laser").state == "on"
    assert hass.states.get("sensor.ncsender_laser_power").state == "80.0"
    await asyncio.sleep(1.2); await hass.async_block_till_done()
    assert hass.states.get("sensor.ncsender_job_progress").state == "42.3"

    # controls: service + button
    await hass.services.async_call(DOMAIN, "send_command", {"command": "M9"}, blocking=True)
    await hass.services.async_call("button", "press", {"entity_id": "button.ncsender_pause_job"}, blocking=True)
    assert fake_ncsender["cmds"][0]["command"] == "M9" and fake_ncsender["cmds"][1] == "PAUSE"

    # availability follows the socket
    await ws.close(); await asyncio.sleep(0.2); await hass.async_block_till_done()
    assert hass.states.get("sensor.ncsender_machine_state").state == "unavailable"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

async def test_cannot_connect(hass, socket_enabled):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"],
        {"host": "127.0.0.1", "port": 18999, "name": "x", "laser_max_s": 1000})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "cannot_connect"}
