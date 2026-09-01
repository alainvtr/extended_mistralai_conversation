# Extended Mistal AI Conversation
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
Extended Mistrail AI Conversation uses Mistal AI API's feature like https://api.mistral.ai/v1/chat/completions.
You can create scripts that can be executed in HA engine when Mistral AI find a match in their description (see some examples in the file mistral_tools.yaml)

## Manual installation
1. Copy `extended_openai_conversation` folder into `<config directory>/custom_components`
2. Restart Home Assistant
   
## Installation via HACS
1. Open HACS in Home Assistant
2. Right top click on the 3 dots and add the personnal repo https://github.com/alainvtr/extended_mistralai_conversation  as an Integration
3. Add and go back to HACS main screen
4. Find Extended Mistal AI Conversation in the available list, select it and add it
5. Restart Home Assistant

## Create a Mistral API key
1. Sign up at mistral.ai : a free account is sufficient
2. Go to console.mistral.ai/api-keys
3. Click Create new key and save it in your favorit secrets tool manager

## Configuration
3. In Home Assistant, go to Settings then Devices & Services and click on Add Integration
4. Search for Extended Mistral AI Conversation
5. Enter your Mistral API key and submit
6. Adapt name and area to your choice and submit
7. Click on the setting gear of the new service Extended Mistral AI Conversation
8. Choose a model among the list available for your account (for a free one, i suggest mistral-small)
9. Review & adapt the other config params to your needs and submit
10. Go to Settings then [Voice Assistants](https://my.home-assistant.io/redirect/voice_assistants/).
11. Click to an existing Assistant or create a new one.
12. Select "Extended Mistral AI Conversation" in "Conversation agent" selector
13. Select "Mistral AI STT" (or other name if you change it before) in "STT" selector
14. Select "Mistral AI TTS" (or other name if you change it before) in "TTS" selector and choose a voice model
15. Submit
16. Edit the file `<config directory>/mistral_prompt.yaml` and adapt to your needs
17. Edit the file `<config directory>/mistral_tools.yaml` and adapt to your needs
18. You have to reload the intégration each time you modify mistral_prompt.yaml or mistral_tools.yaml
    
## Final step
When all is configured, you need to expose entities in  [Voice Assistants]("http://{your-home-assistant}/config/voice-assistants/expose").

### Functions

#### Supported function types
- `native`: built-in function provided by "extended_mistralai_conversation".
  - Currently supported native functions and parameters are:
    - `execute_service`
      - `domain`(string): domain to be passed to `hass.services.async_call`
      - `service`(string): service to be passed to `hass.services.async_call`
      - `service_data`(object): service_data to be passed to `hass.services.async_call`.
        - `entity_id`(string): target entity
        - `device_id`(string): target device
        - `area_id`(string): target area
    - `get_history`
      - `entity_ids`(list): a list of entity ids to filter
      - `start_time`(string): defaults to 1 day before the time of the request. It determines the beginning of the period
      - `end_time`(string): the end of the period in URL encoded format (defaults to 1 day)
      - `minimal_response`(boolean): only return last_changed and state for states other than the first and last state (defaults to true)
      - `no_attributes`(boolean): skip returning attributes from the database (defaults to true)
      - `significant_changes_only`(boolean): only return significant state changes (defaults to true)
- `script`: A list of services that will be called
- `template`: The value to be returned from function.
- `rest`: Getting data from REST API endpoint.
- `scrape`: Scraping information from website
- `composite`: A sequence of functions to execute. 

Below is the minimalistic configuration of functions.

```yaml
- spec:
    name: execute_services
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
                    type: string
                    description: The entity_id retrieved from available devices. It must start with domain, followed by dot character.
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
