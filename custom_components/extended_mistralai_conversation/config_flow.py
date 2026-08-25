"""
    From https://github.com/jekalmin/extended_openai_conversation
    From https://github.com/SnarfNL/HA_MistralAI
Config flow for Mistral AI Conversation integration.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol
import yaml
from homeassistant import config_entries
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .backup import read_json, write_json
from .const import (
    DOMAIN,
    DEFAULT_MODEL,
    DEFAULT_TOOLS_CONFIG_PATH,
    DEFAULT_PROMPT_PATH,
    DEFAULT_ALLOWED_DOMAINS,
    DEFAULT_ALLOWED_SERVICES,
    DEFAULT_BACKUP_PATH,
    MISTRAL_API_BASE,
    STT_MODEL,
    TTS_MODEL,
    CONF_STT_MODEL,
    CONF_TTS_MODEL,
    CONF_TTS_VOICE,
    CONF_TTS_MODE,
    CONF_TTS_HEADROOM,
    CONF_TTS_MAX_INFLIGHT_SENTENCES,
    CONF_TTS_MIN_SENTENCE_CHARS,
    CONF_TTS_SILENCE_MS,
    DEFAULT_TTS_VOICE,
    DEFAULT_TTS_MODE,
    DEFAULT_TTS_HEADROOM,
    DEFAULT_TTS_MAX_INFLIGHT_SENTENCES,
    DEFAULT_TTS_MIN_SENTENCE_CHARS,
    DEFAULT_TTS_SILENCE_MS,
    TTS_MODES,
    TTS_VOICES,
)

_LOGGER = logging.getLogger(__name__)

AUDIO_MODEL_NOTIFICATION_ID = "extended_mistralai_conversation_audio_model_check"


async def _async_fetch_voices(hass: HomeAssistant, api_key: str) -> list[str]:
    """Récupère la liste des voix disponibles depuis l'API Mistral (GET /v1/audio/voices).

    Repli sur la liste statique TTS_VOICES en cas d'échec (réseau, clé
    invalide, timeout, réponse inattendue) — le formulaire d'options ne
    doit jamais se retrouver avec un menu de voix vide.
    """
    if not api_key:
        return TTS_VOICES
    try:
        session = async_get_clientsession(hass)
        async with session.get(
            f"{MISTRAL_API_BASE}/audio/voices",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                _LOGGER.warning(
                    "Impossible de récupérer les voix Mistral (HTTP %s) — repli sur la liste statique",
                    resp.status,
                )
                return TTS_VOICES
            data = await resp.json()
            voices = sorted(item["id"] for item in data.get("items", []) if item.get("id"))
            return voices or TTS_VOICES
    except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as e:
        _LOGGER.warning("Erreur lors de la récupération des voix Mistral : %s — repli sur la liste statique", e)
        return TTS_VOICES


async def _async_fetch_models(hass: HomeAssistant, api_key: str) -> list[str]:
    """Récupère les modèles disponibles pour ce compte (GET /v1/models).

    Filtré sur les modèles utilisables par cette intégration : conversationnels
    (completion_chat) ET compatibles function calling (indispensable pour les
    tools assist_timer/execute_services/etc. — sans ça un modèle sélectionnable
    casserait silencieusement l'appel d'outils), non archivés.

    Repli sur [DEFAULT_MODEL] en cas d'échec (réseau, clé invalide, timeout,
    réponse inattendue) — le formulaire ne doit jamais se retrouver avec un
    menu de modèles vide.
    """
    if not api_key:
        return [DEFAULT_MODEL]
    try:
        session = async_get_clientsession(hass)
        async with session.get(
            f"{MISTRAL_API_BASE}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                _LOGGER.warning(
                    "Impossible de récupérer les modèles Mistral (HTTP %s) — repli sur %s",
                    resp.status,
                    DEFAULT_MODEL,
                )
                return [DEFAULT_MODEL]
            data = await resp.json()
            # L'API renvoie une liste brute selon la doc actuelle, mais on tolère
            # aussi une éventuelle enveloppe {"data": [...]} par prudence.
            items = data if isinstance(data, list) else data.get("data", [])
            models = sorted(
                item["id"]
                for item in items
                if item.get("id")
                and not item.get("archived", False)
                and item.get("capabilities", {}).get("completion_chat")
                and item.get("capabilities", {}).get("function_calling")
            )
            return models or [DEFAULT_MODEL]
    except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as e:
        _LOGGER.warning("Erreur lors de la récupération des modèles Mistral : %s — repli sur %s", e, DEFAULT_MODEL)
        return [DEFAULT_MODEL]


async def _async_check_audio_models(hass: HomeAssistant, api_key: str) -> list[str]:
    """Vérifie que STT_MODEL et TTS_MODEL apparaissent dans /v1/models de ce compte.

    Renvoie la liste des identifiants absents (vide si tout va bien, ou si la
    vérification elle-même a échoué — on ne bloque jamais sur un doute, cette
    fonction est purement informative). Non garanti : rien ne confirme à 100%
    que les modèles audio (Voxtral) sont listés au même endroit que les
    modèles de chat — à vérifier empiriquement une fois déployé.
    """
    if not api_key:
        return []
    try:
        session = async_get_clientsession(hass)
        async with session.get(
            f"{MISTRAL_API_BASE}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            items = data if isinstance(data, list) else data.get("data", [])
            available_ids = {item.get("id") for item in items}
    except (aiohttp.ClientError, TimeoutError, ValueError):
        return []

    return [m for m in (STT_MODEL, TTS_MODEL) if m not in available_ids]


async def _async_fetch_audio_models(hass: HomeAssistant, api_key: str, capability: str, default: str) -> list[str]:
    """Récupère les modèles dont capabilities[capability] est vrai (ex: 'audio_transcription'
    pour le STT, 'audio_speech' pour le TTS). Repli sur [default] en cas d'échec.
    """
    if not api_key:
        return [default]
    try:
        session = async_get_clientsession(hass)
        async with session.get(
            f"{MISTRAL_API_BASE}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return [default]
            data = await resp.json()
            items = data if isinstance(data, list) else data.get("data", [])
            models = sorted(
                item["id"] for item in items
                if item.get("id") and item.get("capabilities", {}).get(capability)
            )
            return models or [default]
    except (aiohttp.ClientError, TimeoutError, ValueError):
        return [default]


async def _async_write_backup(hass: HomeAssistant, path: str, options: dict[str, Any]) -> None:
    """Écrit les options courantes dans le fichier de backup (best-effort : n'empêche jamais la validation)."""
    try:
        await hass.async_add_executor_job(write_json, path, options)
    except OSError as e:
        # Best-effort : un chemin non accessible ne doit pas bloquer la sauvegarde de l'entrée.
        _LOGGER.warning("Impossible d'écrire le backup des options vers %s : %s", path, e)
    else:
        _LOGGER.info("Backup des options écrit avec succès vers %s", path)


async def _async_read_backup(hass: HomeAssistant, path: str) -> dict[str, Any]:
    """Lit le fichier de backup s'il existe, sinon renvoie un dict vide."""
    try:
        return await hass.async_add_executor_job(read_json, path)
    except (OSError, json.JSONDecodeError):
        return {}


class MistralAIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mistral AI Conversation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Chargé une seule fois par tentative de flow, réutilisé entre l'affichage du formulaire et sa validation
        if not hasattr(self, "_backup_options"):
            self._backup_options = await _async_read_backup(self.hass, DEFAULT_BACKUP_PATH)

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("api_key"): str,
                    }
                ),
            )

        backup_path = self._backup_options.get("backup_path", DEFAULT_BACKUP_PATH)
        options = {
            "model": self._backup_options.get("model", DEFAULT_MODEL),
            "tools_config_path": self._backup_options.get("tools_config_path", DEFAULT_TOOLS_CONFIG_PATH),
            "prompt_path": self._backup_options.get("prompt_path", DEFAULT_PROMPT_PATH),
            "allowed_domains": self._backup_options.get("allowed_domains", DEFAULT_ALLOWED_DOMAINS),
            "allowed_services": self._backup_options.get("allowed_services", DEFAULT_ALLOWED_SERVICES),
            CONF_TTS_VOICE: self._backup_options.get(CONF_TTS_VOICE, DEFAULT_TTS_VOICE),
            CONF_TTS_MODE: self._backup_options.get(CONF_TTS_MODE, DEFAULT_TTS_MODE),
            CONF_TTS_HEADROOM: self._backup_options.get(CONF_TTS_HEADROOM, DEFAULT_TTS_HEADROOM),
            CONF_TTS_MAX_INFLIGHT_SENTENCES: self._backup_options.get(
                CONF_TTS_MAX_INFLIGHT_SENTENCES, DEFAULT_TTS_MAX_INFLIGHT_SENTENCES
            ),
            CONF_TTS_MIN_SENTENCE_CHARS: self._backup_options.get(
                CONF_TTS_MIN_SENTENCE_CHARS, DEFAULT_TTS_MIN_SENTENCE_CHARS
            ),
            CONF_TTS_SILENCE_MS: self._backup_options.get(CONF_TTS_SILENCE_MS, DEFAULT_TTS_SILENCE_MS),
            CONF_STT_MODEL: self._backup_options.get(CONF_STT_MODEL, STT_MODEL),
            CONF_TTS_MODEL: self._backup_options.get(CONF_TTS_MODEL, TTS_MODEL),
            "backup_path": backup_path,
        }

        # "Valider" cliqué : sauvegarde systématique. Rien n'est écrit si on ferme via la croix,
        # puisque ce code n'est atteint que lorsque HA appelle ce step avec un user_input rempli.
        await _async_write_backup(self.hass, backup_path, options)

        return self.async_create_entry(
            title="Extended Mistral AI Conversation",
            data={"api_key": user_input["api_key"]},
            options=options,
        )

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(import_config)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MistralOptionsFlowHandler:
        """Create the options flow, permettant de modifier les valeurs par défaut après création."""
        return MistralOptionsFlowHandler()


class MistralOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Extended Mistral AI Conversation.

    Depuis HA récent, self.config_entry est une propriété héritée de OptionsFlow,
    accessible uniquement APRÈS __init__ (jamais dans __init__ lui-même) — donc
    pas de __init__ à définir ici, contrairement aux anciennes versions de HA.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        current = self.config_entry.options
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                allowed_domains = [
                    d.strip() for d in user_input["allowed_domains"].split(",") if d.strip()
                ]
                allowed_services = yaml.safe_load(user_input["allowed_services"]) or {}
                if not isinstance(allowed_services, dict):
                    raise ValueError("allowed_services doit être un mapping YAML (domaine -> liste de services)")
            except Exception as e:
                _LOGGER.error(f"Erreur de validation des options: {e}")
                errors["base"] = "invalid_yaml"
            else:
                options = {
                    "model": user_input["model"],
                    "tools_config_path": user_input["tools_config_path"],
                    "prompt_path": user_input["prompt_path"],
                    "allowed_domains": allowed_domains,
                    "allowed_services": allowed_services,
                    CONF_TTS_VOICE: user_input[CONF_TTS_VOICE],
                    CONF_TTS_MODE: user_input[CONF_TTS_MODE],
                    CONF_TTS_HEADROOM: user_input[CONF_TTS_HEADROOM],
                    CONF_TTS_MAX_INFLIGHT_SENTENCES: int(user_input[CONF_TTS_MAX_INFLIGHT_SENTENCES]),
                    CONF_TTS_MIN_SENTENCE_CHARS: int(user_input[CONF_TTS_MIN_SENTENCE_CHARS]),
                    CONF_STT_MODEL: user_input[CONF_STT_MODEL],
                    CONF_TTS_MODEL: user_input[CONF_TTS_MODEL],
                    CONF_TTS_SILENCE_MS: int(user_input[CONF_TTS_SILENCE_MS]),
                    "backup_path": user_input["backup_path"],
                }
                # "Valider" cliqué : sauvegarde systématique (pas d'écriture si on ferme via la croix).
                # Écrit vers le NOUVEAU backup_path si l'utilisateur vient de le changer dans ce même formulaire.
                await _async_write_backup(self.hass, options["backup_path"], options)
                return self.async_create_entry(title="", data=options)

        api_key = self.config_entry.data.get("api_key")
        voices = await _async_fetch_voices(self.hass, api_key)
        current_voice = current.get(CONF_TTS_VOICE, DEFAULT_TTS_VOICE)
        if current_voice not in voices:
            # Ne jamais laisser le défaut du formulaire hors de la liste d'options —
            # la voix configurée a pu être retirée du catalogue Mistral entre-temps.
            voices = [current_voice] + voices

        models = await _async_fetch_models(self.hass, api_key)
        current_model = current.get("model", DEFAULT_MODEL)
        if current_model not in models:
            models = [current_model] + models

        stt_models = await _async_fetch_audio_models(self.hass, api_key, "audio_transcription", STT_MODEL)
        current_stt_model = current.get(CONF_STT_MODEL, STT_MODEL)
        if current_stt_model not in stt_models:
            stt_models = [current_stt_model] + stt_models

        tts_models = await _async_fetch_audio_models(self.hass, api_key, "audio_speech", TTS_MODEL)
        current_tts_model = current.get(CONF_TTS_MODEL, TTS_MODEL)
        if current_tts_model not in tts_models:
            tts_models = [current_tts_model] + tts_models

        missing_audio_models = await _async_check_audio_models(self.hass, api_key)
        if missing_audio_models:
            persistent_notification.async_create(
                self.hass,
                "Le(s) modèle(s) audio suivant(s) n'apparaissent plus dans /v1/models "
                f"de votre compte : {', '.join(missing_audio_models)}. "
                "Ils sont peut-être dépréciés ou renommés côté Mistral — vérifiez sur "
                "docs.mistral.ai/models et mettez à jour STT_MODEL/TTS_MODEL dans const.py si besoin.",
                title="Extended Mistral AI Conversation — modèle audio introuvable",
                notification_id=AUDIO_MODEL_NOTIFICATION_ID,
            )
        else:
            persistent_notification.async_dismiss(self.hass, AUDIO_MODEL_NOTIFICATION_ID)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("model", default=current_model): SelectSelector(
                        SelectSelectorConfig(options=models, mode=SelectSelectorMode.DROPDOWN, custom_value=True)
                    ),
                    vol.Optional(
                        "tools_config_path",
                        default=current.get("tools_config_path", DEFAULT_TOOLS_CONFIG_PATH),
                    ): str,
                    vol.Optional(
                        "prompt_path",
                        default=current.get("prompt_path", DEFAULT_PROMPT_PATH),
                    ): str,
                    vol.Optional(
                        "allowed_domains",
                        default=", ".join(current.get("allowed_domains", DEFAULT_ALLOWED_DOMAINS)),
                    ): str,
                    vol.Optional(
                        "allowed_services",
                        default=yaml.dump(
                            current.get("allowed_services", DEFAULT_ALLOWED_SERVICES),
                            allow_unicode=True,
                            sort_keys=False,
                        ),
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT, multiline=True)),
                    vol.Optional(
                        "backup_path",
                        default=current.get("backup_path", DEFAULT_BACKUP_PATH),
                    ): str,
                    vol.Optional(
                        CONF_STT_MODEL,
                        default=current_stt_model,
                    ): SelectSelector(
                        SelectSelectorConfig(options=stt_models, mode=SelectSelectorMode.DROPDOWN, custom_value=True)
                    ),
                    vol.Optional(
                        CONF_TTS_MODEL,
                        default=current_tts_model,
                    ): SelectSelector(
                        SelectSelectorConfig(options=tts_models, mode=SelectSelectorMode.DROPDOWN, custom_value=True)
                    ),
                    vol.Optional(
                        CONF_TTS_VOICE,
                        default=current_voice,
                    ): SelectSelector(
                        SelectSelectorConfig(options=voices, mode=SelectSelectorMode.DROPDOWN)
                    ),
                    vol.Optional(
                        CONF_TTS_MODE,
                        default=current.get(CONF_TTS_MODE, DEFAULT_TTS_MODE),
                    ): SelectSelector(
                        SelectSelectorConfig(options=TTS_MODES, mode=SelectSelectorMode.DROPDOWN)
                    ),
                    vol.Optional(
                        CONF_TTS_HEADROOM,
                        default=current.get(CONF_TTS_HEADROOM, DEFAULT_TTS_HEADROOM),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=10, step=0.1, mode=NumberSelectorMode.BOX, unit_of_measurement="dB")
                    ),
                    vol.Optional(
                        CONF_TTS_MAX_INFLIGHT_SENTENCES,
                        default=current.get(CONF_TTS_MAX_INFLIGHT_SENTENCES, DEFAULT_TTS_MAX_INFLIGHT_SENTENCES),
                    ): NumberSelector(
                        NumberSelectorConfig(min=1, max=8, step=1, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional(
                        CONF_TTS_MIN_SENTENCE_CHARS,
                        default=current.get(CONF_TTS_MIN_SENTENCE_CHARS, DEFAULT_TTS_MIN_SENTENCE_CHARS),
                    ): NumberSelector(
                        NumberSelectorConfig(min=1, max=200, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="caractères")
                    ),
                    vol.Optional(
                        CONF_TTS_SILENCE_MS,
                        default=current.get(CONF_TTS_SILENCE_MS, DEFAULT_TTS_SILENCE_MS),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0, max=2000, step=50, mode=NumberSelectorMode.BOX, unit_of_measurement="ms")
                    ),
                }
            ),
            errors=errors,
        )
        
