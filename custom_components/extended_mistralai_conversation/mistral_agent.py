"""
From https://github.com/jekalmin/extended_openai_conversation
Custom Conversation Agent for Mistral AI (HA 2026.7.2).
"""
from __future__ import annotations

import json
import logging
from typing import Literal

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    AssistantContent,
    ConversationEntity,
    ConversationEntityFeature,
    ConversationInput,
    ConversationResult,
    SystemContent,
    ToolResultContent,
    async_get_chat_log,
)
from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.chat_session import async_get_chat_session
from homeassistant.helpers.template import Template
from homeassistant.util import dt as dt_util

from .functions import get_function

_LOGGER = logging.getLogger(__name__)

class MistralConversationAgent(ConversationEntity, conversation.AbstractConversationAgent):
    """Conversation agent for Mistral AI with dynamic prompt and tools."""

    _attr_supported_features = ConversationEntityFeature.CONTROL
    MAX_FUNCTION_CALLS = 5  # <-- garde-fou anti-boucle infinie (cf. jekalmin "Maximum Function Calls Per Conversation")

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api_key: str,
        model: str,
        tools: list[dict],
        prompt_template: str,
        allowed_domains: list[str],
        allowed_services: dict,
    ):
        """Initialize the Mistral conversation agent.

        tools et prompt_template sont déjà chargés depuis le disque par
        async_setup_entry (conversation.py) via l'executor, pour ne jamais
        faire d'I/O bloquant ici : __init__ ne peut pas être async, donc
        aucun hass.async_add_executor_job n'est possible à cet endroit.
        """
        super().__init__()
        self.hass = hass
        self.entry = entry  # <-- Stocke l'entrée de configuration
        self.api_key = api_key
        self.model = model
        self.allowed_domains = allowed_domains
        self.allowed_services = allowed_services
        self.session = async_get_clientsession(hass)  # <-- réutilise la session HA, pas de session orpheline non fermée
        self.tools = tools
        self.prompt_template = prompt_template
        self._attr_name = "Extended Mistral AI Conversation"
        self._attr_unique_id = f"mistral_agent_{entry.entry_id}"  # <-- Utilise entry.entry_id

    @property
    def name(self) -> str:
        """Retourne le nom de l'agent."""
        return self._attr_name

    @property
    def unique_id(self) -> str:
        """Retourne l'ID unique de l'agent."""
        return self._attr_unique_id

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Retourne les langues supportées par l'agent.

        MATCH_ALL (déjà importé, jusque-là inutilisé) plutôt que ["fr"] figé :
        rend l'agent éligible à n'importe quel pipeline Assist, quelle que soit
        sa langue système (hass.config.language) — utile si un second pipeline
        dans une autre langue est créé un jour. Le prompt (static_prompt)
        continue d'imposer des réponses en français indépendamment de ceci ;
        ça ne change rien tant qu'un seul pipeline, en français, existe.
        """
        return MATCH_ALL

    def _get_exposed_entities(self) -> list[dict]:
        """Retourne la liste des entités exposées pour Assist."""
        entity_registry = er.async_get(self.hass)
        exposed = []
        for state in self.hass.states.async_all():
            if not async_should_expose(self.hass, conversation.DOMAIN, state.entity_id):
                continue  # <-- l'exposition Assist se lit via le registre d'entités, pas via state.attributes

            entity = entity_registry.async_get(state.entity_id)
            aliases = [str(a) for a in entity.aliases] if entity and entity.aliases else []

            exposed.append({
                "entity_id": state.entity_id,
                "name": state.name,
                "state": state.state,
                "aliases": aliases
            })
        return exposed

    def _convert_to_mistral_tool(self, tool_config: dict) -> dict:
        """Convertit un tool YAML en format Mistral API.

        .get("parameters", ...) plutôt que ["parameters"] : plusieurs de vos
        tools (allume_pour_canalplus, lancer_musique, alarme_stop, etc.) n'ont
        légitimement aucun argument, donc pas de bloc "parameters" dans le
        YAML — un objet JSON Schema vide est la représentation correcte d'une
        fonction sans paramètres, pas une erreur à faire remonter.
        """
        return {
            "type": "function",
            "function": {
                "name": tool_config["name"],
                "description": tool_config["description"],
                "parameters": tool_config.get("parameters", {"type": "object", "properties": {}})
            }
        }

    async def async_added_to_hass(self) -> None:
        """Appelé quand l'entité est ajoutée à Home Assistant."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)  # <-- rend l'agent sélectionnable dans Assist

    async def async_will_remove_from_hass(self) -> None:
        """Appelé quand l'entité est retirée."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Point d'entrée appelé par Home Assistant."""
        with (
            async_get_chat_session(self.hass, user_input.conversation_id) as session,
            async_get_chat_log(self.hass, session, user_input) as chat_log,
        ):
            intent_response = intent.IntentResponse(language=user_input.language)
            continue_conversation = False
            try:
                rendered_prompt = await self._render_prompt(user_input)
                # Réécrit à chaque tour (le contenu dynamique — états, heure — change), sans toucher
                # au reste de chat_log.content qui, lui, porte l'historique des tours précédents
                chat_log.content[0] = SystemContent(content=rendered_prompt)

                speech = await self._async_conversation_run(chat_log, user_input.context)
                chat_log.async_add_assistant_content_without_tools(
                    AssistantContent(agent_id=self.entity_id, content=speech)
                )  # <-- sans ça, HA jette le chat_log car "aucun contenu assistant ajouté" (voir chat_log.py:131)
                intent_response.async_set_speech(speech)
                # Heuristique simple : une réponse qui se termine par "?" attend probablement une
                # confirmation ("Dans le salon ?") — rouvre le micro plutôt que de couper la conversation.
                # Imparfait (une question rhétorique sans "?" ne serait pas détectée, par exemple),
                # mais couvre le cas le plus courant sans dépendre d'une signalisation explicite de Mistral.
                continue_conversation = speech.rstrip().endswith("?")
            except Exception as e:
                _LOGGER.error(f"Erreur avec Mistral API: {e}")
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    "Désolé, une erreur est survenue avec Mistral AI.",
                )
            return ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id,
                continue_conversation=continue_conversation,
            )

    async def _async_conversation_run(self, chat_log, context: Context | None) -> str:
        """Reconstruit les messages Mistral depuis l'historique complet du chat_log (mémoire multi-tours) et interroge Mistral."""
        mistral_tools = [self._convert_to_mistral_tool(tool) for tool in self.tools]

        # chat_log.content contient : le system prompt courant (position 0, toujours à jour),
        # tous les tours précédents (user/assistant) de cette même conversation_id, et le tour
        # utilisateur courant (ajouté automatiquement par async_get_chat_log avant qu'on arrive ici).
        # getattr(..., "content", None) exclut proprement les ToolResultContent (pas d'attribut
        # "content", ils ont "tool_result") sans avoir à importer UserContent pour un isinstance().
        messages = [
            {"role": content.role, "content": content.content}
            for content in chat_log.content
            if getattr(content, "content", None)
        ]

        return await self._query_mistral(messages, mistral_tools, n_calls=0, context=context, chat_log=chat_log)

    async def _query_mistral(
        self,
        messages: list[dict],
        mistral_tools: list[dict],
        n_calls: int,
        context: Context | None,
        chat_log,
    ) -> str:
        """Appelle Mistral, exécute les tool_calls demandés, et relance jusqu'à obtenir une réponse texte."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": mistral_tools,
            "prompt_cache_key": self._attr_unique_id,  # <-- clé stable par agent (pas par conversation) : maximise les hits sur le préfixe statique du prompt, identique entre toutes les conversations
        }

        async with self.session.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            json=payload
        ) as response:
            response_data = await response.json()

        message = response_data["choices"][0]["message"]  # <-- tool_calls est niché ici, pas sur "choices"[0] directement
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            # Réponse texte finale : c'est Mistral qui formule, selon les instructions du prompt
            return message.get("content", "")

        if n_calls >= self.MAX_FUNCTION_CALLS:
            _LOGGER.warning("Nombre maximum d'appels de fonction atteint (%s)", self.MAX_FUNCTION_CALLS)
            return "Désolé, je n'arrive pas à terminer cette action."

        # L'historique doit inclure le message assistant contenant les tool_calls avant les réponses "tool"
        messages.append(message)

        # Rend l'appel de fonction visible dans le debug Assist (events intent-progress).
        # external=True : on exécute nous-mêmes ces tool_calls (pas via l'API llm interne de HA),
        # c'est la condition exigée par async_add_assistant_content_without_tools pour les accepter.
        tool_inputs = [
            llm.ToolInput(
                id=tool_call["id"],
                tool_name=tool_call["function"]["name"],
                tool_args=json.loads(tool_call["function"]["arguments"]),
                external=True,
            )
            for tool_call in tool_calls
        ]
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(agent_id=self.entity_id, content=message.get("content"), tool_calls=tool_inputs)
        )

        for tool_call, tool_input in zip(tool_calls, tool_inputs):
            result_text = await self._execute_function(tool_input.tool_name, tool_input.tool_args, context)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": tool_input.tool_name,
                "content": result_text,
            })
            chat_log.async_add_assistant_content_without_tools(
                ToolResultContent(
                    agent_id=self.entity_id,
                    tool_call_id=tool_input.id,
                    tool_name=tool_input.tool_name,
                    tool_result={"result": result_text},
                )
            )

        # On relance Mistral avec les résultats, pour qu'il formule la réponse finale
        return await self._query_mistral(messages, mistral_tools, n_calls + 1, context, chat_log)

    async def _execute_function(self, function_name: str, arguments: dict, context: Context | None) -> str:
        """Trouve la config du tool et délègue à l'exécuteur du type correspondant (native/script/template/rest/scrape/composite)."""
        tool_config = next((t for t in self.tools if t["name"] == function_name), None)
        if not tool_config:
            return f"Tool {function_name} non trouvé."

        function_config = tool_config["function"]
        function_type = function_config.get("type", "template")

        # Garde-fou spécifique à execute_service : liste blanche domaines/services.
        # Absent de extended_openai_conversation, conservé ici car c'était déjà votre logique.
        if function_type == "native" and function_config.get("name") == "execute_service":
            for service_call in arguments.get("list", []):
                domain = service_call["domain"]
                service = service_call["service"]
                if domain not in self.allowed_domains:
                    return f"Le domaine {domain} n'est pas autorisé."
                if service not in self.allowed_services.get(domain, []):
                    return f"Le service {service} pour le domaine {domain} n'est pas autorisé."

        try:
            executor = get_function(function_type)
            result = await executor.execute(
                self.hass, function_config, arguments, context, self._get_exposed_entities()
            )
        except Exception as e:
            _LOGGER.error(f"Erreur lors de l'exécution de {function_name} ({function_type}): {e}")
            return f"Erreur : {e}"

        if isinstance(result, str):
            return result
        return json.dumps(result, default=str, ensure_ascii=False)

    async def _render_prompt(self, user_input: ConversationInput | None = None) -> str:
        """Rend le prompt complet avec Jinja2."""
        template_vars = {
            "now": dt_util.now,
            "exposed_entities": self._get_exposed_entities(),  # <-- résolu ici (liste), pas une référence de fonction — comme extended_openai_conversation, pas de () requis dans le prompt
            # "areas" et "area_name" ne sont plus injectées ici : elles masquaient les
            # fonctions natives Jinja de HA (areas()/area_name()) avec nos propres versions
            # plus limitées — area_name() en particulier, qui ne savait résoudre qu'un
            # area_id littéral, jamais un device_id ni un entity_id, contrairement à la
            # native qui gère les trois avec résolution en cascade entité → appareil.
            "states": self.hass.states.get,
            "user_input": user_input,
        }

        template = Template(self.prompt_template, self.hass)
        return template.async_render(variables=template_vars)
        
