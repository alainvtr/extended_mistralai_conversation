"""Fonctions natives Home Assistant : execute_service, get_history.

Sous-ensemble volontairement limité de ce que propose extended_openai_conversation
(qui gère aussi add_automation, get_energy, get_statistics, get_user_from_user_id).
"""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components import recorder
from homeassistant.components.recorder import history as recorder_history
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
import homeassistant.util.dt as dt_util

from .base import Function

_LOGGER = logging.getLogger(__name__)


class NativeFunction(Function):
    """Dispatch sur function_config['name']."""

    async def execute(
        self,
        hass: HomeAssistant,
        function_config: dict[str, Any],
        arguments: dict[str, Any],
        context: Context | None,
        exposed_entities: list[dict[str, Any]],
    ) -> Any:
        name = function_config["name"]
        if name == "execute_service":
            return await self.execute_service(hass, arguments, exposed_entities)
        if name == "get_history":
            return await self.get_history(hass, arguments, exposed_entities)
        raise HomeAssistantError(
            f"Fonction native '{name}' non supportée (seules execute_service et get_history le sont)."
        )

    async def execute_service_single(
        self,
        hass: HomeAssistant,
        service_argument: dict[str, Any],
        exposed_entities: list[dict[str, Any]],
    ) -> dict[str, Any]:
        domain = service_argument["domain"]
        service = service_argument["service"]
        service_data = service_argument.get("service_data", {})

        # device_id/area_id ciblent des entités qui ne passent jamais par validate_entity_ids
        # ci-dessous (seul entity_id y est soumis) — un area_id en particulier atteindrait
        # TOUTES les entités de la zone, exposées ou non. Bloqué explicitement plutôt que
        # transmis tel quel à hass.services.async_call, qui les honorerait sans contrôle.
        if "device_id" in service_data or "area_id" in service_data:
            return {"error": "device_id et area_id ne sont pas autorisés : cible uniquement via entity_id."}

        entity_id = service_data.get("entity_id")

        if isinstance(entity_id, str):
            entity_id = [e.strip() for e in entity_id.split(",")]
            service_data["entity_id"] = entity_id

        if not hass.services.has_service(domain, service):
            raise ServiceNotFound(domain, service)
        if entity_id:
            self.validate_entity_ids(hass, entity_id, exposed_entities)

        try:
            await hass.services.async_call(domain=domain, service=service, service_data=service_data)
            return {"success": True}
        except HomeAssistantError as e:
            _LOGGER.error(e)
            return {"error": str(e)}

    async def execute_service(
        self,
        hass: HomeAssistant,
        arguments: dict[str, Any],
        exposed_entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            await self.execute_service_single(hass, service_argument, exposed_entities)
            for service_argument in arguments.get("list", [])
        ]

    async def get_history(
        self,
        hass: HomeAssistant,
        arguments: dict[str, Any],
        exposed_entities: list[dict[str, Any]],
    ) -> list[list[dict[str, Any]]]:
        start_time = arguments.get("start_time")
        end_time = arguments.get("end_time")
        entity_ids = arguments.get("entity_ids", [])

        now = dt_util.utcnow()
        one_day = timedelta(days=1)
        start = self._as_utc(start_time, now - one_day, "start_time invalide")
        end = self._as_utc(end_time, start + one_day, "end_time invalide")

        self.validate_entity_ids(hass, entity_ids, exposed_entities)

        with recorder.util.session_scope(hass=hass, read_only=True) as session:
            result = await recorder.get_instance(hass).async_add_executor_job(
                recorder_history.get_significant_states_with_session,
                hass,
                session,
                start,
                end,
                entity_ids,
                None,
                True,   # include_start_time_state
                True,   # significant_changes_only
                True,   # minimal_response
                True,   # no_attributes
            )

        return [[self._as_dict(item) for item in sublist] for sublist in result.values()]

    def _as_utc(self, value: str | None, default_value: Any, error_message: str) -> Any:
        if value is None:
            return default_value
        parsed = dt_util.parse_datetime(value)
        if parsed is None:
            raise HomeAssistantError(error_message)
        return dt_util.as_utc(parsed)

    def _as_dict(self, state: State | dict[str, Any]) -> dict[str, Any]:
        return state.as_dict() if isinstance(state, State) else state
