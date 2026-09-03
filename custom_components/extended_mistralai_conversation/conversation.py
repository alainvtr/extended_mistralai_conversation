"""
From https://github.com/jekalmin/extended_openai_conversation
Conversation platform for Mistral AI.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import yaml
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    DEFAULT_MODEL,
    DEFAULT_TOOLS_CONFIG_PATH,
    DEFAULT_PROMPT_PATH,
    DEFAULT_ALLOWED_DOMAINS,
    DEFAULT_ALLOWED_SERVICES,
)
from .mistral_agent import MistralConversationAgent

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = "extended_mistralai_conversation_tools_error"

# Modèles livrés avec l'intégration (dossier default_config/, voyage avec le dépôt/HACS),
# copiés vers /config UNIQUEMENT s'il n'existe pas déjà de fichier à cet emplacement.
DEFAULT_CONFIG_DIR = Path(__file__).parent / "default_config"

# Types de fonctions supportés par functions/__init__.py (FUNCTIONS) — tenu à jour manuellement,
# sqlite/bash/read_file/write_file volontairement laissés de côté pour le moment.
SUPPORTED_FUNCTION_TYPES = {"native", "script", "template", "rest", "scrape", "composite"}

# Clés minimales attendues dans function_config selon le type, pour détecter au chargement
# les erreurs qui sinon ne se révéleraient qu'au moment où le LLM tente d'appeler l'outil
REQUIRED_FUNCTION_KEYS = {
    "native": ["name"],
    "script": ["sequence"],
    "template": ["value_template"],
    "composite": ["sequence"],
    # "rest" et "scrape" traités à part ci-dessous : resource / resource_template sont
    # deux alternatives valides (voir functions/web.py::_get_rest_data)
}


class ToolsConfigError(Exception):
    """Erreur de configuration dans mistral_tools.yaml (syntaxe ou structure)."""


def _validate_tool(index: int, tool: dict[str, Any]) -> list[str]:
    """Valide un tool et renvoie la liste des erreurs trouvées (vide si tout va bien)."""
    errors: list[str] = []
    label = f"tool #{index}"

    if not isinstance(tool, dict):
        return [f"{label} : doit être un mapping YAML, trouvé {type(tool).__name__}"]

    name = tool.get("name")
    if not name:
        errors.append(f"{label} : clé 'name' manquante")
    else:
        label = f"tool '{name}'"

    if "description" not in tool:
        errors.append(f"{label} : clé 'description' manquante")

    function_config = tool.get("function")
    if not isinstance(function_config, dict):
        errors.append(f"{label} : clé 'function' manquante ou n'est pas un mapping")
        return errors

    function_type = function_config.get("type")
    if function_type not in SUPPORTED_FUNCTION_TYPES:
        errors.append(
            f"{label} : function.type '{function_type}' inconnu ou non supporté "
            f"(supportés : {', '.join(sorted(SUPPORTED_FUNCTION_TYPES))})"
        )
        return errors

    if function_type in ("rest", "scrape"):
        if "resource" not in function_config and "resource_template" not in function_config:
            errors.append(
                f"{label} : function.resource ou function.resource_template manquant (requis pour le type '{function_type}')"
            )
        if function_type == "scrape" and "sensor" not in function_config:
            errors.append(f"{label} : function.sensor manquant (requis pour le type 'scrape')")

    for required_key in REQUIRED_FUNCTION_KEYS.get(function_type, []):
        if required_key not in function_config:
            errors.append(f"{label} : function.{required_key} manquant (requis pour le type '{function_type}')")

    return errors


def _load_tools_config(path: str) -> list[dict]:
    """Charge et valide mistral_tools.yaml (fonction synchrone, à exécuter via l'executor).

    Lève ToolsConfigError avec un message détaillé en cas de problème, plutôt que
    d'avaler l'erreur et de démarrer silencieusement avec zéro tool.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except OSError as e:
        raise ToolsConfigError(f"Impossible de lire {path} : {e}") from e
    except yaml.YAMLError as e:
        raise ToolsConfigError(f"Erreur de syntaxe YAML dans {path} :\n{e}") from e

    if config is None:
        raise ToolsConfigError(f"{path} est vide ou ne contient pas de clé 'tools'.")

    tools = config.get("tools")
    if not isinstance(tools, list):
        raise ToolsConfigError(f"{path} : la clé 'tools' doit être une liste, trouvé {type(tools).__name__}.")

    all_errors: list[str] = []
    for index, tool in enumerate(tools):
        all_errors.extend(_validate_tool(index, tool))

    if all_errors:
        raise ToolsConfigError(
            f"{len(all_errors)} erreur(s) dans {path} :\n" + "\n".join(f"  - {e}" for e in all_errors)
        )

    _LOGGER.info("%s : %d tool(s) chargé(s) avec succès depuis %s", DOMAIN, len(tools), path)
    return tools


def _load_prompt_template(path: str) -> str:
    """Charge et assemble le prompt (YAML static_prompt + dynamic_prompt) depuis le disque (fonction synchrone, à exécuter via l'executor)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        static_prompt = config.get("static_prompt", "")
        dynamic_prompt = config.get("dynamic_prompt", "")
        return f"{static_prompt}\n{dynamic_prompt}"
    except Exception as e:
        _LOGGER.error(f"Erreur lors du chargement de {path}: {e}")
        return ""


def _ensure_default_file(target_path: str, source_path: Path) -> None:
    """Copie le fichier modèle vers target_path UNIQUEMENT s'il n'existe pas déjà
    (fonction synchrone, à exécuter via l'executor). Ne touche jamais à un fichier
    déjà présent — pas d'écrasement d'une config personnalisée.
    """
    target = Path(target_path)
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, target)
    _LOGGER.info("%s : première installation, %s créé à partir du modèle par défaut", DOMAIN, target)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mistral AI conversation platform."""
    api_key = entry.data.get("api_key")
    model = entry.options.get("model", DEFAULT_MODEL)
    # hass.config.path() résout un chemin relatif par rapport à /config, et laisse un
    # chemin déjà absolu inchangé — gère donc les deux cas correctement (contrairement
    # à un open() direct sur un chemin relatif, qui dépend du cwd du process HA).
    tools_config_path = hass.config.path(entry.options.get("tools_config_path", DEFAULT_TOOLS_CONFIG_PATH))
    prompt_path = hass.config.path(entry.options.get("prompt_path", DEFAULT_PROMPT_PATH))
    allowed_domains = entry.options.get("allowed_domains", DEFAULT_ALLOWED_DOMAINS)
    allowed_services = entry.options.get("allowed_services", DEFAULT_ALLOWED_SERVICES)

    if not api_key:
        _LOGGER.error("API key for Mistral AI is not configured.")
        return

    await hass.async_add_executor_job(
        _ensure_default_file, tools_config_path, DEFAULT_CONFIG_DIR / DEFAULT_TOOLS_CONFIG_PATH
    )
    await hass.async_add_executor_job(
        _ensure_default_file, prompt_path, DEFAULT_CONFIG_DIR / DEFAULT_PROMPT_PATH
    )

    prompt_template = await hass.async_add_executor_job(_load_prompt_template, prompt_path)

    try:
        tools = await hass.async_add_executor_job(_load_tools_config, tools_config_path)
    except ToolsConfigError as e:
        # Visible dans l'UI (cloche de notifications HA), pas seulement dans les logs.
        # L'agent démarre quand même, avec zéro tool, plutôt que de bloquer toute la conversation.
        persistent_notification.async_create(
            hass,
            f"L'agent Mistral a démarré **sans aucun outil** (impossible d'utiliser vos fonctions)"
            f" car son chargement a échoué :\n\n```\n{e}\n```\n\n"
            f"Corrigez `{tools_config_path}` puis rechargez l'intégration.",
            title="Extended Mistral AI Conversation — erreur de configuration",
            notification_id=NOTIFICATION_ID,
        )
        _LOGGER.error(str(e))
        tools = []
    else:
        # En cas de succès après une précédente erreur, on efface la notification devenue obsolète
        persistent_notification.async_dismiss(hass, NOTIFICATION_ID)

    agent = MistralConversationAgent(
        hass=hass,
        entry=entry,
        api_key=api_key,
        model=model,
        tools=tools,
        prompt_template=prompt_template,
        allowed_domains=allowed_domains,
        allowed_services=allowed_services,
    )

    async_add_entities([agent])
