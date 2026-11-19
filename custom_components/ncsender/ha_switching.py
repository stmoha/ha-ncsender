"""Switching allowlisted HA entities for ncSender.

Two ways in, one set of rules:
- "(HA <entity_id> ON|OFF|TOGGLE)" comment lines that the controller acknowledged
  (seen in ncSender's command stream; needs the controller on and not in Hold).
- A local-only webhook the HA Switches plugin posts to directly, so its buttons work
  with the controller off, before homing, in an alarm and while a job is paused.

Only entities in the "Devices ncSender may switch" option are touched. Every request
fires an `ncsender_ha_command` event, allowed or not.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import web

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .client import HA_ACTIONS
from .const import CONF_HA_SWITCHES, CONF_WEBHOOK_ID, DOMAIN, EVENT_HA_COMMAND

_LOGGER = logging.getLogger(__name__)

# The plugin runs in ncSender's page, a different origin from HA, and posts text/plain
# (a "simple" request, so no CORS preflight). HA's webhook view already allows CORS from
# any origin. Never set Access-Control-* headers here: aiohttp_cors asserts they're unset
# and drops the connection when a browser (which always sends Origin) calls.


def allowed_entities(entry: ConfigEntry) -> list[str]:
    return list(entry.options.get(CONF_HA_SWITCHES) or [])


async def async_switch(
    hass: HomeAssistant, entry: ConfigEntry, entity_id: str, service: str, source: str
) -> str | None:
    """Call homeassistant.<service> for an allowlisted entity. Returns an error, or None."""
    is_allowed = entity_id in allowed_entities(entry)
    hass.bus.async_fire(
        EVENT_HA_COMMAND,
        {"entity_id": entity_id, "service": service, "allowed": is_allowed, "source": source},
    )
    if not is_allowed:
        _LOGGER.warning(
            "Ignoring ncSender %s for %s: not in the integration's allowed entities "
            "(Settings → ncSender → Configure)",
            service,
            entity_id,
        )
        return "not allowed: add it under ncSender → Configure → Devices ncSender may switch"
    try:
        await hass.services.async_call(
            "homeassistant", service, {"entity_id": entity_id}, blocking=True
        )
    except HomeAssistantError as err:
        _LOGGER.warning("ncSender %s %s failed: %s", service, entity_id, err)
        return str(err) or "failed"
    return None


def comment_handler(hass: HomeAssistant, entry: ConfigEntry):
    """Listener for the client's acknowledged "(HA …)" lines."""

    @callback
    def _handle(entity_id: str, service: str) -> None:
        hass.async_create_task(async_switch(hass, entry, entity_id, service, "command"))

    return _handle


def _states(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for entity_id in allowed_entities(entry):
        state = hass.states.get(entity_id)
        out[entity_id] = {
            "state": state.state if state else "unknown",
            "name": state.name if state else entity_id,
        }
    return out


def _reply(status: int, body: dict[str, Any]) -> web.Response:
    return web.json_response(body, status=status)


def ensure_webhook_id(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """The entry's webhook ID, created once and kept, so the plugin's URL stays valid."""
    webhook_id = entry.data.get(CONF_WEBHOOK_ID)
    if not webhook_id:
        webhook_id = webhook.async_generate_id()
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_WEBHOOK_ID: webhook_id}
        )
    return webhook_id


def webhook_url(hass: HomeAssistant, webhook_id: str) -> str:
    """The LAN URL to paste into the plugin (falls back to just the path)."""
    path = webhook.async_generate_path(webhook_id)
    try:
        return get_url(hass, allow_external=False, allow_cloud=False) + path
    except NoURLAvailableError:
        return path


def register_webhook(hass: HomeAssistant, entry: ConfigEntry) -> callback:
    """Register the plugin's webhook; returns the unregister callback."""
    webhook_id = ensure_webhook_id(hass, entry)

    async def _handle(hass: HomeAssistant, _webhook_id: str, request: web.Request) -> web.Response:
        try:
            body = json.loads(await request.text() or "{}")
        except ValueError:
            return _reply(400, {"ok": False, "error": "body is not JSON"})
        if not isinstance(body, dict):
            return _reply(400, {"ok": False, "error": "body must be a JSON object"})

        action = str(body.get("action", "")).upper()
        if action == "STATES":
            return _reply(200, {"ok": True, "states": _states(hass, entry)})

        service = HA_ACTIONS.get(action)
        entity_id = str(body.get("entity_id", "")).strip().lower()
        if service is None or not entity_id:
            return _reply(
                400, {"ok": False, "error": 'expected {"entity_id": …, "action": "on|off|toggle"}'}
            )
        error = await async_switch(hass, entry, entity_id, service, "webhook")
        if error:
            return _reply(403 if error.startswith("not allowed") else 502, {"ok": False, "error": error})
        state = hass.states.get(entity_id)
        return _reply(200, {"ok": True, "entity_id": entity_id, "state": state.state if state else None})

    webhook.async_register(
        hass,
        DOMAIN,
        "ncSender HA Switches",
        webhook_id,
        _handle,
        local_only=True,
        allowed_methods=["POST"],
    )

    @callback
    def _unregister() -> None:
        webhook.async_unregister(hass, webhook_id)

    return _unregister
