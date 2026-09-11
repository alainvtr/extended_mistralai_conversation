# Extended Mistral AI Conversation
This is a custom component for Home Assistant.

Derived from [Extended OpenAI Conversation](https://github.com/jekalmin/extended_openai_conversation) and adapted to specific Mistal AI API.\
TTS and STT from [Mistral AI Conversation](https://github.com/SnarfNL/HA_MistralAI) are also provided to have a full package to use with Mistral AI.\
The TTS sound from Mistral is very low compared to other TTS like Microsoft, Google, Open AI : so, a sound boost (normalize()) is done on the TTS.

## Features
- Ability to call service of Home Assistant
- Ability to get data from external API or web page
- Ability to retrieve state history of entities
- TTS
- STT
- the prompt for the LLM, stored in `<config directory>/mistral_prompt.yaml` (a sample is provided), is divided in 2 parts :
   - static prompt under `static_prompt: |`
   - dynamic prompt under `dynamic_prompt: |`
- the tools/functions (scripts) called by the LLM are stored in `<config directory>/mistral_tools.yaml`
- all the configuration parameters are backuped in `<share directory>/ext_mistral_conv_opt.json` (each time you validate the configuration of the service)
  
## How it works
Extended Mistral AI Conversation uses Mistral AI API's feature like https://api.mistral.ai/v1/chat/completions.  \
You can create scripts that can be executed in HA engine when Mistral AI finds a match in their description (see some examples in the file mistral_tools.yaml)

## Manual installation
1. Copy `extended_mistralai_conversation` folder into `<config directory>/custom_components`
2. Restart Home Assistant
   
## Installation via HACS
1. Open HACS in Home Assistant
2. Right top click on the 3 dots and add the personal repo https://github.com/alainvtr/extended_mistralai_conversation  as an Integration
3. Add and go back to HACS main screen
4. Find Extended Mistral AI Conversation in the available list, select it and add it
5. Restart Home Assistant

## Create a Mistral API key
1. Sign up at mistral.ai : a free account is generally sufficient (see notes at the end)
2. Go to console.mistral.ai/api-keys
3. Click Create new key and save it in your favorite secrets tool manager

## Configuration
1. In Home Assistant, go to Settings then Devices & Services and click on Add Integration
2. Search for Extended Mistral AI Conversation
3. Enter your Mistral API key and submit (Note: this integration reads the API key from the config flow form directly — secrets.yaml is not supported here)
4. Adapt name and area to your choice and submit or ignore and terminate
5. Click on the setting gear of the new service Extended Mistral AI Conversation
6. Choose a model among the list available for your account (for a free one, i suggest mistral-small-latest)
7. Review & adapt the other config params (see explanation below) to your needs and submit
8. Go to Settings then [Voice Assistants](https://my.home-assistant.io/redirect/voice_assistants/).
9. Click to an existing Assistant or create a new one.
10. Select "Extended Mistral AI Conversation" in "Conversation agent" selector
11. Select "Mistral AI STT (Voxtral)" (or other name if you change it before) in "STT" selector
12. Select "Mistral AI TTS" (or other name if you change it before) in "TTS" selector and choose a voice model
13. Submit
14. Edit the file `<config directory>/mistral_prompt.yaml` and adapt to your needs
15. Edit the file `<config directory>/mistral_tools.yaml` and adapt to your needs
16. You have to reload the integration each time you modify mistral_prompt.yaml or mistral_tools.yaml
    
## Final step
When all is configured, you need to expose entities in  [Voice Assistants](https://my.home-assistant.io/redirect/voice-assistants/expose).

## Functions or tools (in `<config directory>/mistral_tools.yaml`)

### Supported types
- `native`: built-in function provided by "extended_mistralai_conversation".
  - Currently supported native functions and parameters are:
    - `execute_service`
      - `domain`(string): domain to be passed to `hass.services.async_call`
      - `service`(string): service to be passed to `hass.services.async_call`
      - `service_data`(object): service_data to be passed to `hass.services.async_call`.
        - `entity_id`(string): target entity
        - (device_id and area_id are explicitly rejected — entity_id only, so every target is always checked against Assist exposure)
    - `get_history`
      - `entity_ids`(list): a list of entity ids to filter
      - `start_time`(string): defaults to 1 day before the time of the request. It determines the beginning of the period
      - `end_time`(string): the end of the period in URL encoded format (defaults to 1 day)
- `script`: It's like a script in HA (action, choose, if/then/else, repeat, ...) - The LLM wait for the end of the script to say something
- `template`: The value to be returned from function.
- `rest`: Getting data from REST API endpoint.
- `scrape`: Scraping information from website
- `composite`: A sequence of functions (template, rest, scrape, script )to execute. 

Below is the minimalistic configuration.

```yaml

- name: execute_services
  description: Use this function to execute service of devices in Home Assistant.
  parameters:
    type: object
    properties:
      list:
        type: array
        items:
          type: object
          properties:
            domain:
              type: string
              description: The domain of the service
            service:
              type: string
              description: The service to be called
            service_data:
              type: object
              description: The service data object to indicate what to control.
              properties:
                entity_id:
                  type: array
                  items:
                    type: string
                  description: List of target entity_id
              required:
                - entity_id
          required:
            - domain
            - service
            - service_data
  function:
    type: native
    name: execute_service
```

### Some explanations on the 'tools' type

#### Where should a script live: `scripts.yaml` or `mistral_tools.yaml`?

The LLM can trigger a Home Assistant script in two different ways:

- **As an exposed entity**, via the generic `execute_services` tool (already defined in `mistral_tools.yaml` by default). If the script is defined in `scripts.yaml` and exposed to Assist, its `description:` field is automatically picked up and included in the "Available Devices" list of the dynamic prompt. If that description is clear enough, the LLM can decide on its own to call it (`domain: script`, `service: turn_on`, `entity_id: script.xxx`) — no dedicated tool entry needed for that script specifically.
- **As a dedicated tool** in `mistral_tools.yaml`, with its own `sequence:`. In this case the script logic lives entirely inside the tool definition — it is never registered as a `script.xxx` entity and never appears among your Home Assistant scripts.

#### How to choose

1. **If the script needs to be called from elsewhere** (another script, an automation, a dashboard button) — it must be a real script in `scripts.yaml`. A `sequence:` embedded directly in `mistral_tools.yaml` is not a registered entity and cannot be referenced anywhere else.
2. **If you rely on Home Assistant's native execution traces** (Settings > Automations & Scenes > Scripts > *your script* > Traces) — only a real script in `scripts.yaml` gets this. A tool's inline `sequence:` runs through a temporary script object created at call time; it is never registered, so it never shows up in the Traces UI. (Not to be confused with the `get_history` tool, which reads *entity state* history from the recorder — a different Home Assistant feature entirely.)
3. **If the script takes input parameters** (`fields:` in `scripts.yaml`): they are **never** visible to the LLM through the "exposed entity" path, no matter how good the script's `description` is — Home Assistant's service-description cache only exposes the script's own text description, not its individual `fields:`. To let the LLM actually provide arguments, you need a dedicated tool in `mistral_tools.yaml` with a proper `parameters:` schema. From there, the tool's `sequence:` can either hold the full script logic directly, or simply call your existing `script.xxx` — pick based on points 1 and 2 above.
4. **If the script has an output text response meant to be used by the LLM**: it is **never** visible to the LLM through the "exposed entity" path, because calling a script that way is **fire and forget** — it always returns `{"success": true}`, whatever happens inside the script. To make a script's output reach the LLM, two things are required: the script itself must produce a value via a `- stop:` action with `response_variable:` at the end of its own sequence in `scripts.yaml`, **and** the calling tool in `mistral_tools.yaml` must capture it with its own `response_variable:` on the `- action:` step that calls it (see the `lancer_musique` example below).

You can find some examples in the provided mistral_tools.yaml. \
Don't forget that the 'description' field is very important for the LLM: it provides guidance on what to do and how to behave in specific situations.

   - The `add_event`, `assist_timer`, `add_one_note`, `list_all_notes` show how you can use the "script" function type.
   - The `get_weather`, `search_brave` show how you can use the "rest" function type.
   - The `get_attributes`, `get_tcl_maison_to_cisl`, `get_tcl_cisl_to_maison` show how you can use the "template" function type.
   - The `get_event` show how you can use the "composite" function type.
   - The `lancer_musique`, `surveille_charge` show how you can pass to the LLM a specific execution result from the called script. Then, the TTS can say this result. The script must end with something like :
```yaml     
        - variables:
            resultat:
              message: "Voilà, c'est fait."
        - stop: "réponse renvoyée au LLM"
          response_variable: resultat
```
   - The `get_history` show how you can use the native "get_history" function type.

## Explanations for the configuration parameters

| Parameter | Default | Explanation |
|---|---|---|
| `model` | *(dynamic dropdown)* | Chat model used for conversation. Populated live from `GET /v1/models`, filtered to models with both `completion_chat` and `function_calling` capabilities (required for tool use) and not archived. |
| `tools_config_path` | `mistral_tools.yaml` | Path to your tools definition file. Resolved relative to `<config directory>` if not absolute. Copied from a bundled template on first install if missing. |
| `prompt_path` | `mistral_prompt.yaml` | Path to your prompt file (YAML with `static_prompt`/`dynamic_prompt` keys — see below). Same resolution/first-install behavior as `tools_config_path`. |
| `allowed_domains` | `light, cover, script, media_player` | Domain whitelist for the `execute_services` tool. A domain not listed here is refused outright, regardless of what's exposed to Assist — this only applies to the generic `execute_services` tool, not to dedicated `type: script` tools. |
| `allowed_services` | see YAML below | Service whitelist **per domain**, for the `execute_services` tool. Independent from entity exposure: a service call that targets a script by its own service name (e.g. `service: my_script`, no `entity_id`) bypasses Assist exposure entirely — this whitelist is the only guard on that path. Keep the `script` domain limited to `turn_on`/`turn_off`/`toggle` unless you have a specific reason to widen it. |
| `backup_path` | `/share/ext_mistralai_conv_opt.json` | Where your options (this whole table, minus the API key) are backed up on every "Submit", and restored from on fresh install. Must be a path genuinely shared between the Home Assistant Core container and wherever you inspect it — `/backup` is **not** reliably shared on HAOS, `/share` is. |
| `tts_voice` | `fr_marie_neutral` | Default Voxtral voice. Populated live from `GET /v1/audio/voices` (your account's available presets, including any cloned voices). |
| `tts_mode` | `stream` | `stream`: sentence-pipelined, lower time-to-first-audio, higher complexity. `batch`: single request/response, simpler, higher latency on long replies. |
| `tts_headroom` | `2.6` dB | Target headroom for audio normalization (`pydub.effects.normalize`) — lower value = louder output. Mistral's TTS output is notably quieter than Microsoft/Google/OpenAI by default, hence the boost. |
| `tts_max_inflight_sentences` | `2` | Max concurrent Mistral TTS requests in `stream` mode (one per sentence). Higher = faster overall synthesis on long replies, at the cost of more simultaneous API calls. |
| `tts_min_sentence_chars` | `12` | Minimum sentence length before triggering a TTS call in `stream` mode — avoids firing a request for short fragments. |
| `tts_silence_ms` | `300` ms | Silence inserted between sentences in `stream` mode, for a natural pause at sentence boundaries. |
| `stt_model` | *(dynamic dropdown)* | Transcription model. Populated live from `GET /v1/models`, filtered to `capabilities.audio_transcription` (excludes the separate realtime-only variant). |
| `tts_model_id` | *(dynamic dropdown)* | Speech synthesis model. Populated live from `GET /v1/models`, filtered to `capabilities.audio_speech`. |

`allowed_services` default value, in YAML:

```yaml
light:
  - turn_on
  - turn_off
  - toggle
cover:
  - open_cover
  - close_cover
  - set_cover_position
script:
  - turn_on
  - turn_off
  - toggle
media_player:
  - volume_set
  - media_play_pause
  - turn_on
  - turn_off
```

## A note on free-tier rate limits

If you're on Mistral's free Studio access and start seeing conversations silently fail (or STT/TTS working while the conversation agent doesn't), check your logs for something like:

```
Erreur avec Mistral API: Mistral API a renvoyé 429 : {"object":"error","message":"Rate limit exceeded","type":"rate_limited",...}
```

This is expected behavior on the free tier, not a bug in this integration. Free access to Mistral's API works on a **best-effort basis**: there is no reserved capacity for free users. When paying customers are using a given model, free-tier requests can be rejected — including your very first request of the day, with no prior usage on your account. \
You can confirm this is what's happening by checking the response headers of a failed request (`x-ratelimit-limit-req-minute: 0` is the tell-tale sign of a free account with no currently available capacity, as opposed to an account that has genuinely exhausted a real quota). \
CURL command to test : 

```
curl -i https://api.mistral.ai/v1/chat/completions \
  -H "Authorization: Bearer VOTRE_CLE_API" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral-small-latest",
    "messages": [{"role": "user", "content": "Bonjour"}]
  }'
```

A few things worth knowing:

- **This is per model / per endpoint**, not account-wide. You may see `chat/completions` fail while `audio/speech` (TTS) works fine, or one model family (e.g. `magistral-*`) fail while another (`mistral-*`) succeeds — each can have its own capacity situation at any given moment.
- **Free-tier credits are not consumed while your account is in this "Pending/free" status.** Credits only start being used once you're on a paid plan that guarantees capacity — a failed free-tier request costs you nothing.
- This integration already includes automatic retry with exponential backoff on HTTP 429 (see `MAX_RETRIES_429` in `mistral_agent.py`) to smooth over short-lived spikes. It helps with occasional contention, but it's not a substitute for reserved capacity — during sustained heavy load from paying customers, retries can still exhaust their budget and fail.

**If reliability matters to you** (e.g. you're using this for a real voice assistant, not just experimenting), switch to Mistral's **Pay-as-you-go** plan on [console.mistral.ai](https://console.mistral.ai). It gives you reserved capacity and priority access, and you're only billed for what you actually use — for a typical home voice assistant, the monthly cost is usually small.
