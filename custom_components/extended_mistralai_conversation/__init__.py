"""
From https://github.com/jekalmin/extended_openai_conversation
From https://github.com/SnarfNL/HA_MistralAI
Mistral AI Conversation Agent for Home Assistant 2026.7.2.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .backup import read_json, write_json
from .const import DOMAIN, DEFAULT_BACKUP_PATH, DEFAULT_TOOLS_CONFIG_PATH

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["conversation", "tts", "stt"]

SERVICE_EXPORT_OPTIONS = "export_options"
SERVICE_IMPORT_OPTIONS = "import_options"
SERVICE_GET_TOOLS = "get_tools"

SERVICE_PATH_SCHEMA = vol.Schema(
    {vol.Optional("path"): cv.string}
)


def _get_single_entry(hass: HomeAssistant) -> ConfigEntry:
    """Retourne l'unique config entry de cette intégration (erreur claire sinon)."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("Aucune intégration Extended Mistral AI Conversation configurée.")
    if len(entries) > 1:
        raise ServiceValidationError(
            "Plusieurs intégrations Extended Mistral AI Conversation trouvées : ce service ne gère qu'une seule entrée."
        )
    return entries[0]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up via configuration.yaml (legacy) + enregistrement des services."""

    async def _handle_export(call: ServiceCall) -> None:
        entry = _get_single_entry(hass)
        # Défaut résolu ici (pas dans le schéma) : suit backup_path si modifié via l'Options Flow,
        # plutôt que de rester figé sur la constante d'origine.
        path = call.data.get("path") or entry.options.get("backup_path", DEFAULT_BACKUP_PATH)
        # data (api_key) volontairement exclu : /share peut être synchronisé
        # vers un cloud, on ne veut pas y laisser le token en clair.
        try:
            await hass.async_add_executor_job(write_json, path, dict(entry.options))
        except OSError as e:
            raise ServiceValidationError(f"Écriture impossible vers {path} : {e}") from e
        _LOGGER.info("Options Extended Mistral AI Conversation exportées vers %s", path)

    async def _handle_import(call: ServiceCall) -> None:
        entry = _get_single_entry(hass)
        path = call.data.get("path") or entry.options.get("backup_path", DEFAULT_BACKUP_PATH)
        try:
            options = await hass.async_add_executor_job(read_json, path)
        except (OSError, json.JSONDecodeError) as e:
            raise ServiceValidationError(f"Lecture impossible depuis {path} : {e}") from e
        if not isinstance(options, dict):
            raise ServiceValidationError(f"Le fichier {path} ne contient pas un objet JSON valide.")
        hass.config_entries.async_update_entry(entry, options=options)
        _LOGGER.info("Options Extended Mistral AI Conversation importées depuis %s", path)

    async def _handle_get_tools(call: ServiceCall) -> dict[str, Any]:
        # Import tardif : évite un import circulaire au chargement du module (conversation.py
        # importe déjà des choses de ce package)
        from .conversation import ToolsConfigError, _load_tools_config

        entry = _get_single_entry(hass)
        tools_config_path = entry.options.get("tools_config_path", DEFAULT_TOOLS_CONFIG_PATH)
        try:
            tools = await hass.async_add_executor_job(_load_tools_config, tools_config_path)
        except ToolsConfigError as e:
            raise ServiceValidationError(str(e)) from e

        return {
            "count": len(tools),
            "tools": [
                {"name": t["name"], "description": t.get("description", ""), "type": t["function"]["type"]}
                for t in tools
            ],
        }

    hass.services.async_register(DOMAIN, SERVICE_EXPORT_OPTIONS, _handle_export, schema=SERVICE_PATH_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_IMPORT_OPTIONS, _handle_import, schema=SERVICE_PATH_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_GET_TOOLS, _handle_get_tools, supports_response=SupportsResponse.ONLY
    )
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Mistral AI conversation agent from a config entry."""
    # Déléguer la configuration à la plateforme conversation
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Recharge l'intégration si les options sont modifiées (Options Flow ou import_options)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge l'entrée quand les options changent."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
