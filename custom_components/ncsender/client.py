"""ncSender WebSocket/REST client.

Mirrors ncSender's `server-state-updated` stream into a derived snapshot
that entities read from, and exposes the REST control endpoints.

Protocol (verified against ncSender source, community edition, Sep 2026):
  - WS at ws://host:port/  — envelope {"type": ..., "data": ...}
  - Full ServerState on connect, then shallow deltas (nested objects contain
    only changed keys; jobLoaded may become null).
  - cnc-command-result broadcasts every acknowledged command.
  - REST: /api/health, /api/server-state, /api/send-command,
    /api/gcode-job/{pause,resume,stop}
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .const import DEFAULT_TELEMETRY_INTERVAL, SOURCE_ID

_LOGGER = logging.getLogger(__name__)

# Keys whose change is pushed immediately (state-like). Everything else in
# the snapshot is telemetry and is throttled with a trailing flush.
IMMEDIATE_KEYS = frozenset(
    {
        "machine_state",
        "sender_status",
        "connected",
        "spindle",
        "laser",
        "laser_power",
        "active_output",
        "flood_coolant",
        "mist_coolant",
        "job_status",
        "job_file",
        "alarm",
        "workspace",
        "workspace_attributes",
        "tool_change",
        "tool_change_attributes",
        "tool",
        "tool_attributes",
    }
)

_M_CODE = re.compile(r"(?<![A-Za-z0-9.])M0*(\d+)(?!\d)", re.IGNORECASE)
_T_WORD = re.compile(r"(?<![A-Za-z])T\s*0*(\d+)", re.IGNORECASE)


def _q(value: float, step: float) -> float | int:
    """Quantize to a step; integers for whole steps."""
    q = round(value / step) * step
    return int(q) if float(step).is_integer() else round(q, 1)


class NcSenderClient:
    """Maintains the ncSender connection and derived state."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        laser_max_s: float,
        telemetry_interval: float = DEFAULT_TELEMETRY_INTERVAL,
    ) -> None:
        self._session = session
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.ws_url = f"ws://{host}:{port}/?product={SOURCE_ID}"
        self.laser_max_s = float(laser_max_s)
        self.telemetry_interval = float(telemetry_interval)

        self.connected = False
        self.state: dict[str, Any] = {}  # mirrored raw ServerState
        self.data: dict[str, Any] = {}  # published derived snapshot
        self.coolant: dict[str, bool | None] = {"flood": None, "mist": None}
        self._alarm: str | None = None
        self.tools: list[dict[str, Any]] = []
        self.last_tool_change: dict[str, Any] | None = None  # set on each acknowledged M6

        self._listeners: set[Callable[[], None]] = set()
        self._task: asyncio.Task | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._last_push = 0.0
        self._flush_handle: asyncio.TimerHandle | None = None

    # ------------------------------------------------------------------ listeners
    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(callback)

        def _remove() -> None:
            self._listeners.discard(callback)

        return _remove

    def _notify(self) -> None:
        for callback in list(self._listeners):
            callback()

    # ------------------------------------------------------------------ lifecycle
    async def async_test_connection(self) -> bool:
        try:
            async with self._session.get(
                f"{self.base_url}/api/health", timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                return resp.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.get_running_loop().create_task(self._run())

    async def async_stop(self) -> None:
        self._cancel_flush()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._set_connected(False)

    def _set_connected(self, value: bool) -> None:
        if self.connected != value:
            self.connected = value
            self._notify()

    async def _run(self) -> None:
        backoff = 1
        while True:
            try:
                _LOGGER.debug("Connecting to %s", self.ws_url)
                async with self._session.ws_connect(
                    self.ws_url, heartbeat=20, timeout=aiohttp.ClientWSTimeout(ws_close=10)
                ) as ws:
                    self._ws = ws
                    backoff = 1
                    # Server sends full state on connect; start clean.
                    self.state.clear()
                    self._cancel_flush()
                    self._set_connected(True)
                    _LOGGER.info("Connected to ncSender at %s:%s", self.host, self.port)
                    asyncio.get_running_loop().create_task(self._async_fetch_tools())
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            self._handle_message(msg.data)
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
                _LOGGER.debug("ncSender connection error: %s", err)
            finally:
                self._ws = None
            if self.connected:
                _LOGGER.warning("Lost connection to ncSender at %s:%s", self.host, self.port)
            self._set_connected(False)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

    # ------------------------------------------------------------------ messages
    def _handle_message(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        mtype, payload = msg.get("type"), msg.get("data")

        if mtype == "server-state-updated" and isinstance(payload, dict):
            ms_delta = payload.get("machineState")
            if isinstance(ms_delta, dict):
                # A flood/mist value appearing in a delta is a real transition
                # parsed from an A: field — trust it over the command shadow.
                if "floodCoolant" in ms_delta:
                    self.coolant["flood"] = bool(ms_delta["floodCoolant"])
                if "mistCoolant" in ms_delta:
                    self.coolant["mist"] = bool(ms_delta["mistCoolant"])
            self._merge_delta(payload)
            self._publish()
        elif mtype == "cnc-command-result" and isinstance(payload, dict):
            if payload.get("status") == "success":
                command = str(payload.get("command") or "")
                self._track_coolant_command(command, str(payload.get("displayCommand") or ""))
                self._track_tool_change_command(command)
                self._publish()
        elif mtype == "cnc-error":
            self._alarm = payload if isinstance(payload, str) else json.dumps(payload)
            self._publish()
        elif mtype == "tools-updated" and isinstance(payload, list):
            self.tools = payload
            self._publish()

    async def _async_fetch_tools(self) -> None:
        try:
            async with self._session.get(
                f"{self.base_url}/api/tools", timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, list):
                        self.tools = data
                        self._publish(force=True)
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            _LOGGER.debug("Could not fetch tool library: %s", err)

    def _merge_delta(self, delta: dict[str, Any]) -> None:
        """Shallow nested merge, mirroring ncSender's StateDeltaTracker."""
        for key, value in delta.items():
            if isinstance(value, dict) and isinstance(self.state.get(key), dict):
                self.state[key].update(value)
            else:
                self.state[key] = value

    def _track_coolant_command(self, command: str, display: str) -> None:
        """ncSender preserves accessory flags when grbl omits the A: field
        (whenever no accessory is on), so the final all-off transition is
        lost. Track acknowledged M-codes to cover it."""
        if "\x18" in command or "0x18" in display or "0x18" in command:
            self.coolant["flood"] = False
            self.coolant["mist"] = False
            return
        for m in _M_CODE.finditer(command):
            code = int(m.group(1))
            if code == 8:
                self.coolant["flood"] = True
            elif code == 7:
                self.coolant["mist"] = True
            elif code in (9, 2, 30):
                self.coolant["flood"] = False
                self.coolant["mist"] = False

    def _track_tool_change_command(self, command: str) -> None:
        """Record each acknowledged M6 — fires before the swap, independent of
        how the sender or an ATC plugin tracks tool-change state afterwards."""
        if not any(int(m.group(1)) == 6 for m in _M_CODE.finditer(command)):
            return
        t = _T_WORD.search(command)
        requested = int(t.group(1)) if t else None
        self.last_tool_change = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "requested_tool": requested,
            "previous_tool": (self.state.get("machineState") or {}).get("tool"),
            "command": command.strip(),
        }

    # ------------------------------------------------------------------ derivation
    @staticmethod
    def _axes(csv: Any) -> list[float]:
        try:
            return [float(v) for v in str(csv).split(",")]
        except ValueError:
            return []

    def _snapshot(self) -> dict[str, Any]:
        ms = self.state.get("machineState") or {}
        job = self.state.get("jobLoaded")

        rpm_target = float(ms.get("spindleRpmTarget") or 0)
        rpm_actual = float(ms.get("spindleRpmActual") or 0)
        # Require nonzero RPM alongside the (possibly stale) accessory flag;
        # also correctly reports ON while the spindle coasts down.
        output_active = bool(ms.get("spindleActive")) and (rpm_target > 0 or rpm_actual > 0)
        # PWM laser commands S in its power scale and has no RPM feedback;
        # the VFD targets thousands of RPM and reports actual via Modbus.
        laser_on = output_active and rpm_target <= self.laser_max_s and rpm_actual == 0
        spindle_on = output_active and not laser_on

        flood = self.coolant["flood"]
        if flood is None:
            flood = bool(ms.get("floodCoolant"))
        mist = self.coolant["mist"]
        if mist is None:
            mist = bool(ms.get("mistCoolant"))

        axes = str(ms.get("axes") or "XYZ").upper()
        mpos = self._axes(ms.get("MPos", ""))
        wpos = self._axes(ms.get("WPos", ""))

        def axis(vals: list[float], i: int) -> float | None:
            return vals[i] if len(vals) > i else None

        def by_axis(vals: list[float]) -> dict[str, float | None]:
            return {letter.lower(): axis(vals, i) for i, letter in enumerate(axes)}

        workspaces = {
            ws: by_axis(self._axes(ms[ws]))
            for ws in ("g54", "g55", "g56", "g57", "g58", "g59")
            if ms.get(ws)
        }

        tool_number = ms.get("tool")
        tool_match = next(
            (t for t in self.tools if t.get("toolNumber") == tool_number), None
        ) or next(
            (t for t in self.tools if (t.get("toolId") or t.get("id")) == tool_number), None
        )
        pockets = {
            str(t["toolNumber"]): t.get("name") or f"tool {t.get('toolId') or t.get('id')}"
            for t in sorted(self.tools, key=lambda t: t.get("toolNumber") or 0)
            if t.get("toolNumber") is not None
        }

        snap: dict[str, Any] = {
            "machine_state": str(ms.get("status") or "Unknown"),
            "sender_status": str(self.state.get("senderStatus") or "unknown"),
            "connected": bool(ms.get("connected")),
            "spindle": spindle_on,
            "laser": laser_on,
            "laser_power": round(rpm_target / self.laser_max_s * 100, 1) if laser_on else 0,
            "active_output": "laser" if laser_on else ("spindle" if spindle_on else "off"),
            "flood_coolant": flood,
            "mist_coolant": mist,
            "alarm": self._alarm or "none",
            "axes": axes,
            "workspace": str(ms.get("workspace") or "unknown"),
            "workspace_attributes": workspaces,
            "tool": tool_number,
            "tool_attributes": {
                "name": (tool_match or {}).get("name"),
                "tool_id": (tool_match or {}).get("toolId") or (tool_match or {}).get("id"),
                "pocket": (tool_match or {}).get("toolNumber"),
                "type": (tool_match or {}).get("type"),
                "diameter": (tool_match or {}).get("diameter"),
                "tlo": ((tool_match or {}).get("offsets") or {}).get("tlo"),
                "life_remaining_min": ((tool_match or {}).get("life") or {}).get("remainingMinutes"),
                "tool_length_set": ms.get("toolLengthSet"),
                "tool_changing": ms.get("isToolChanging"),
                "pockets": pockets,
            },
            # Telemetry is quantized: RPM/feed to 10s, positions to 0.01 mm,
            # so sensor jitter doesn't generate recorder rows.
            "tool_change": (self.last_tool_change or {}).get("at"),
            "tool_change_attributes": self.last_tool_change or {},
            "spindle_rpm": _q(rpm_actual, 10),
            "spindle_rpm_target": _q(rpm_target, 10),
            "feed_rate": _q(float(ms.get("feedRate") or 0), 10),
            "machine_attributes": {
                "homed": ms.get("homed"),
                "workspace": ms.get("workspace"),
                "tool": ms.get("tool"),
                "feed_override": ms.get("feedrateOverride"),
                "rapid_override": ms.get("rapidOverride"),
                "spindle_override": ms.get("spindleOverride"),
                "pins": ms.get("Pn"),
            },
        }

        for letter, value in by_axis(mpos).items():
            snap[f"mpos_{letter}"] = None if value is None else round(value, 2)
        for letter, value in by_axis(wpos).items():
            snap[f"wpos_{letter}"] = None if value is None else round(value, 2)

        if job:
            rem = job.get("remainingSec")
            snap.update(
                {
                    "job_status": str(job.get("status") or "loaded"),
                    "job_file": str(job.get("filename") or "none"),
                    "job_progress": _q(float(job.get("progressPercent") or 0), 0.5),
                    "job_remaining": _q(float(rem), 10) if rem is not None else 0,
                    "job_attributes": {
                        "current_line": job.get("currentLine"),
                        "total_lines": job.get("totalLines"),
                        "runtime_sec": round(float(job.get("runtimeSec") or 0)),
                        "started_at": job.get("jobStartTime"),
                        "ended_at": job.get("jobEndTime"),
                    },
                }
            )
        else:
            snap.update(
                {
                    "job_status": "none",
                    "job_file": "none",
                    "job_progress": 0,
                    "job_remaining": 0,
                    "job_attributes": {},
                }
            )
        return snap

    def _publish(self, force: bool = False) -> None:
        snap = self._snapshot()
        immediate_changed = any(snap.get(k) != self.data.get(k) for k in IMMEDIATE_KEYS)
        now = time.monotonic()
        if force or immediate_changed or (now - self._last_push) >= self.telemetry_interval:
            self._cancel_flush()
            self._last_push = now
            if snap != self.data:
                self.data = snap
                self._notify()
            return
        if snap != self.data:
            self._schedule_flush(self.telemetry_interval - (now - self._last_push))

    def _schedule_flush(self, delay: float) -> None:
        if self._flush_handle is not None:
            return

        def _run_flush() -> None:
            self._flush_handle = None
            self._publish(force=True)

        self._flush_handle = asyncio.get_running_loop().call_later(max(delay, 0.05), _run_flush)

    def _cancel_flush(self) -> None:
        if self._flush_handle:
            self._flush_handle.cancel()
            self._flush_handle = None

    # ------------------------------------------------------------------ control
    async def _post(self, path: str, body: dict[str, Any] | None = None) -> None:
        """POST to ncSender; every failure surfaces as NcSenderError so callers
        (buttons, the send_command service) can show a clean message."""
        try:
            async with self._session.post(
                f"{self.base_url}{path}", json=body, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise NcSenderError(f"ncSender rejected {path} ({resp.status}): {text[:200]}")
        except asyncio.TimeoutError as err:
            raise NcSenderError(
                f"Timed out contacting ncSender at {self.host}:{self.port}"
            ) from err
        except aiohttp.ClientError as err:
            raise NcSenderError(
                f"Cannot reach ncSender at {self.host}:{self.port}: {err}"
            ) from err

    async def async_send_command(self, command: str) -> None:
        await self._post("/api/send-command", {"command": command, "sourceId": SOURCE_ID})

    async def async_pause(self) -> None:
        await self._post("/api/gcode-job/pause")

    async def async_resume(self) -> None:
        await self._post("/api/gcode-job/resume")

    async def async_stop_job(self) -> None:
        await self._post("/api/gcode-job/stop")


class NcSenderError(Exception):
    """Raised when ncSender rejects a control request."""
