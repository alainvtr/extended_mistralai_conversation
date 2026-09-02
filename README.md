# Extended Mistral AI Conversation
This is a custom component for Home Assistant.

Derived from [Extended OpenAI Conversation](https://github.com/jekalmin/extended_openai_conversation) and adapted to specific Mistal AI API.
And i've added TTS and STT from [Mistral AI Conversation](https://github.com/SnarfNL/HA_MistralAI) to have a full package to use with Mistral AI.
The TTS sound from Mistral is very low compared to other TTS like Microsoft, Google, Open AI : so, a sound boost (normalize()) is done on the TTS.

## Features
- Ability to call service of Home Assistant
- Ability to get data from external API or web page
- Ability to retrieve state history of entities
- TTS
- STT

## How it works
Extended Mistral AI Conversation uses Mistral AI API's feature like https://api.mistral.ai/v1/chat/completions.
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
1. Sign up at mistral.ai : a free account is sufficient
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

### Functions

#### Supported function types
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
- `script`: A list of services that will be called
- `template`: The value to be returned from function.
- `rest`: Getting data from REST API endpoint.
- `scrape`: Scraping information from website
- `composite`: A sequence of functions to execute. 

Below is the minimalistic configuration of functions.

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
You can find some examples in the provided mistral_tools.yaml.

# Configuration parameters

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
