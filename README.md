# Extended Mistal AI Conversation
This is a custom component for Home Assistant.

Derived from [Extended OpenAI Conversation][https://github.com/jekalmin/extended_openai_conversation] and adapted to specific Mistal AI API.
And i've added TTS and STT from [Mistral AI Conversation][https://github.com/SnarfNL/HA_MistralAI] to have a full package to use with Mistral AI. The TTS from Mistral is very low compared to other TTS like Microsoft, Google, Open AI : so, a sound boost (normalize()) is done on the TTS.

## Features
- Ability to call service of Home Assistant
- Ability to get data from external API or web page
- Ability to retrieve state history of entities
- TTS
- STT

## How it works
Extended Mistrail AI Conversation uses Mistal AI API's feature like https://api.mistral.ai/v1/chat/completions.
You can create scripts that Mistral AI can execute when their description match (see the content of mistral_tools.yaml)

## Manual installation
1. Copy `extended_openai_conversation` folder into `<config directory>/custom_components`
2. Copy the 2 files in `extended_openai_conversation/default_config` folder into `<config directory>`
3. Restart Home Assistant
   
## Installation via HACS
1. Open HACS in Home Assistant
2. Right top clic on the 3 dots and add the personnal repo https://github.com/alainvtr/extended_mistralai_conversation  as an Integration
3. Add and go back to HACS main screen
4. Find Extended Mistal AI Conversation in the available list, select it and then add it
5. Restart Home Assistant

## Create a Mistral API key
1. Sign up at mistral.ai
2. Go to console.mistral.ai/api-keys
2. Click Create new key and copy it immediately

## Configuration

1. Edit the file `<config directory>/mistral_prompt.txt` and adapt to your needs
2. Edit the file `<config directory>/mistral_tools.yaml` and adapt to your needs
3. Settings → Devices & Services → + Add Integration
4. Search for Extended Mistral AI Conversation
5. Enter your API key → Submit
6. Review & adapt the other config params to your needs
7. Validate
8. Go to Settings > [Voice Assistants](https://my.home-assistant.io/redirect/voice_assistants/).
11. Click to edit Assistant (named "Home Assistant" by default).
12. Select "Extended MistralAI Conversation" from "Conversation agent" tab.
    
## Final step
After installed, you need to expose entities from "http://{your-home-assistant}/config/voice-assistants/expose".


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

Below is a default configuration of functions.

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

#### Specification (Spec)
Specification is a [function schema](https://platform.openai.com/docs/guides/function-calling#defining-functions) defined by openai which will be passed to LLM as a tool.

Reserved Parameters:
- `delay`: If specified, function will be executed in background after a delay. See [example](https://github.com/jekalmin/extended_openai_conversation/tree/main/examples/function/timer).
  - ```yaml
    delay:
      type: object
      description: Time to wait before execution
      properties:
        hours:
          type: integer
          minimum: 0
        minutes:
          type: integer
          minimum: 0
        seconds:
          type: integer
          minimum: 0
    ```

## Function Usage
This is an example of configuration of functions.

Copy and paste below yaml configuration into "Functions".<br/>
Then you will be able to let OpenAI call your function. 

### 1. template
#### 1-1. Get current weather

For real world example, see [weather](https://github.com/jekalmin/extended_openai_conversation/tree/main/examples/function/weather).<br/>
This is just an example from [OpenAI documentation](https://platform.openai.com/docs/guides/function-calling/common-use-cases)

```yaml
- spec:
    name: get_current_weather
    description: Get the current weather in a given location
    parameters:
      type: object
      properties:
        location:
          type: string
          description: The city and state, e.g. San Francisco, CA
        unit:
          type: string
          enum:
          - celcius
          - farenheit
      required:
      - location
  function:
    type: template
    value_template: The temperature in {{ location }} is 25 {{unit}}
```

<img width="300" alt="스크린샷 2023-10-07 오후 7 56 27" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/05e31ea5-daab-4759-b57d-9f5be546bac8">

### 2. script
#### 2-1. Add item to shopping cart
```yaml
- spec:
    name: add_item_to_shopping_cart
    description: Add item to shopping cart
    parameters:
      type: object
      properties:
        item:
          type: string
          description: The item to be added to cart
      required:
      - item
  function:
    type: script
    sequence:
    - service: shopping_list.add_item
      data:
        name: '{{item}}'
```

<img width="300" alt="스크린샷 2023-10-07 오후 7 54 56" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/89060728-4703-4e57-8423-354cdc47f0ee">

#### 2-2. Send messages to another messenger

In order to accomplish "send it to Line" like [example3](https://github.com/jekalmin/extended_openai_conversation#3-hook-with-custom-notify-function), register a notify function like below.

```yaml
- spec:
    name: send_message_to_line
    description: Use this function to send message to Line.
    parameters:
      type: object
      properties:
        message:
          type: string
          description: message you want to send
      required:
      - message
  function:
    type: script
    sequence:
    - service: script.notify_all
      data:
        message: "{{ message }}"
```

<img width="300" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/16dc4ca0-c823-4dfe-a2b7-1ba7623acc70">

#### 2-3. Get events from calendar

In order to pass result of calling service to OpenAI, set response variable to `_function_result`. 

```yaml
- spec:
    name: get_events
    description: Use this function to get list of calendar events.
    parameters:
      type: object
      properties:
        start_date_time:
          type: string
          description: The start date time in '%Y-%m-%dT%H:%M:%S%z' format
        end_date_time:
          type: string
          description: The end date time in '%Y-%m-%dT%H:%M:%S%z' format
      required:
      - start_date_time
      - end_date_time
  function:
    type: script
    sequence:
    - service: calendar.get_events
      data:
        start_date_time: "{{start_date_time}}"
        end_date_time: "{{end_date_time}}"
      target:
        entity_id:
        - calendar.[YourCalendarHere]
        - calendar.[MoreCalendarsArePossible]
      response_variable: _function_result
```

<img width="300" alt="스크린샷 2023-10-31 오후 9 04 56" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/7a6c6925-a53e-4363-a93c-45f63951d41b">

#### 2-4. Play Youtube on TV

```yaml
- spec:
    name: play_youtube
    description: Use this function to play Youtube.
    parameters:
      type: object
      properties:
        video_id:
          type: string
          description: The video id.
      required:
      - video_id
  function:
    type: script
    sequence:
    - service: webostv.command
      data:
        entity_id: media_player.{YOUR_WEBOSTV}
        command: system.launcher/launch
        payload:
          id: youtube.leanback.v4
          contentId: "{{video_id}}"
    - delay:
        hours: 0
        minutes: 0
        seconds: 10
        milliseconds: 0
    - service: webostv.button
      data:
        entity_id: media_player.{YOUR_WEBOSTV}
        button: ENTER
```

<img width="300" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/d5c9e0db-8d7c-4a7a-bc46-b043627ffec6">

#### 2-5. Play Netflix on TV

```yaml
- spec:
    name: play_netflix
    description: Use this function to play Netflix.
    parameters:
      type: object
      properties:
        video_id:
          type: string
          description: The video id.
      required:
      - video_id
  function:
    type: script
    sequence:
    - service: webostv.command
      data:
        entity_id: media_player.{YOUR_WEBOSTV}
        command: system.launcher/launch
        payload:
          id: netflix
          contentId: "m=https://www.netflix.com/watch/{{video_id}}"
```

<img width="300" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/346065d3-7ab9-49c8-ba30-b79b37a5f084">

### 3. native

#### 3-1. Add automation

Before adding automation, I highly recommend set notification on `automation_registered_via_extended_openai_conversation` event and create separate "Extended OpenAI Assistant" and "Assistant"

(Automation can be added even if conversation fails because of failure to get response message, not automation)

| Create Assistant                                                                                                                             | Notify on created                                                                                                                                                              |
|----------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| <img width="830" alt="1" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/b7030a46-9a4e-4ea8-a4ed-03d2eb3af0a9"> | <img width="1116" alt="스크린샷 2023-10-13 오후 6 01 40" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/7afa3709-1c1d-41d0-8847-70f2102d824f"> |


Copy and paste below configuration into "Functions"

**For English**
```yaml
- spec:
    name: add_automation
    description: Use this function to add an automation in Home Assistant.
    parameters:
      type: object
      properties:
        automation_config:
          type: string
          description: A configuration for automation in a valid yaml format. Next line character should be \n. Use devices from the list.
      required:
      - automation_config
  function:
    type: native
    name: add_automation
```

**For Korean**
```yaml
- spec:
    name: add_automation
    description: Use this function to add an automation in Home Assistant.
    parameters:
      type: object
      properties:
        automation_config:
          type: string
          description: A configuration for automation in a valid yaml format. Next line character should be \\n, not \n. Use devices from the list.
      required:
      - automation_config
  function:
    type: native
    name: add_automation
```

<img width="300" alt="스크린샷 2023-10-31 오후 9 32 27" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/55f5fe7e-b1fd-43c9-bce6-ac92e203598f">

#### 3-2. Get History
Get state history of entities

```yaml
- spec:
    name: get_history
    description: Retrieve historical data of specified entities.
    parameters:
      type: object
      properties:
        entity_ids:
          type: array
          items:
            type: string
            description: The entity id to filter.
        start_time:
          type: string
          description: Start of the history period in "%Y-%m-%dT%H:%M:%S%z".
        end_time:
          type: string
          description: End of the history period in "%Y-%m-%dT%H:%M:%S%z".
      required:
      - entity_ids
  function:
    type: composite
    sequence:
      - type: native
        name: get_history
        response_variable: history_result
      - type: template
        value_template: >-
          {% set ns = namespace(result = [], list = []) %}
          {% for item_list in history_result %}
              {% set ns.list = [] %}
              {% for item in item_list %}
                  {% set last_changed = item.last_changed | as_timestamp | timestamp_local if item.last_changed else None %}
                  {% set new_item = dict(item, last_changed=last_changed) %}
                  {% set ns.list = ns.list + [new_item] %}
              {% endfor %}
              {% set ns.result = ns.result + [ns.list] %}
          {% endfor %}
          {{ ns.result }}
```

<img width="300" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/32217f3d-10fc-4001-9028-717b1683573b">

### 4. scrape
#### 4-1. Get current HA version
Scrape version from webpage, "https://www.home-assistant.io"

Unlike [scrape](https://www.home-assistant.io/integrations/scrape/), "value_template" is added at root level in which scraped data from sensors are passed.

```yaml
- spec:
    name: get_ha_version
    description: Use this function to get Home Assistant version
    parameters:
      type: object
      properties:
        dummy:
          type: string
          description: Nothing
  function:
    type: scrape
    resource: https://www.home-assistant.io
    value_template: "version: {{version}}, release_date: {{release_date}}"
    sensor:
      - name: version
        select: ".current-version h1"
        value_template: '{{ value.split(":")[1] }}'
      - name: release_date
        select: ".release-date"
        value_template: '{{ value.lower() }}'
```

<img width="300" alt="스크린샷 2023-10-31 오후 9 46 07" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/e640c3f3-8d68-486b-818e-bd81bf71c2f7">

### 5. rest
#### 5-1. Get friend names
- Sample URL: https://jsonplaceholder.typicode.com/users
```yaml
- spec:
    name: get_friend_names
    description: Use this function to get friend_names
    parameters:
      type: object
      properties:
        dummy:
          type: string
          description: Nothing.
  function:
    type: rest
    resource: https://jsonplaceholder.typicode.com/users
    value_template: '{{value_json | map(attribute="name") | list }}'
```

<img width="300" alt="스크린샷 2023-10-31 오후 9 48 36" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/f968e328-5163-4c41-a479-76a5406522c1">


### 6. composite
#### 6-1. Search Youtube Music
When using [ytube_music_player](https://github.com/KoljaWindeler/ytube_music_player), after `ytube_music_player.search` service is called, result is stored in attribute of `sensor.ytube_music_player_extra` entity.<br/>


```yaml
- spec:
    name: search_music
    description: Use this function to search music
    parameters:
      type: object
      properties:
        query:
          type: string
          description: The query
      required:
      - query
  function:
    type: composite
    sequence:
    - type: script
      sequence:
      - service: ytube_music_player.search
        data:
          entity_id: media_player.ytube_music_player
          query: "{{ query }}"
    - type: template
      value_template: >-
        media_content_type,media_content_id,title
        {% for media in state_attr('sensor.ytube_music_player_extra', 'search') -%}
          {{media.type}},{{media.id}},{{media.title}}
        {% endfor%}
```

<img width="300" alt="스크린샷 2023-11-02 오후 8 40 36" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/648efef8-40d1-45d2-b3f9-9bac4a36c517">

### 7. sqlite
#### 7-1. Let model generate a query
- Without examples, a query tries to fetch data only from "states" table like below
  > Question: When did bedroom light turn on? <br/>
    Query(generated by gpt): SELECT * FROM states WHERE entity_id = 'input_boolean.livingroom_light_2' AND state = 'on' ORDER BY last_changed DESC LIMIT 1
- Since "entity_id" is stored in "states_meta" table, we need to give examples of question and query.
- Not secured, but flexible way

```yaml
- spec:
    name: query_histories_from_db
    description: >-
      Use this function to query histories from Home Assistant SQLite database.
      Example:
        Question: When did bedroom light turn on?
        Answer: SELECT datetime(s.last_updated_ts, 'unixepoch', 'localtime') last_updated_ts FROM states s INNER JOIN states_meta sm ON s.metadata_id = sm.metadata_id INNER JOIN states old ON s.old_state_id = old.state_id WHERE sm.entity_id = 'light.bedroom' AND s.state = 'on' AND s.state != old.state ORDER BY s.last_updated_ts DESC LIMIT 1
        Question: Was livingroom light on at 9 am?
        Answer: SELECT datetime(s.last_updated_ts, 'unixepoch', 'localtime') last_updated, s.state FROM states s INNER JOIN states_meta sm ON s.metadata_id = sm.metadata_id INNER JOIN states old ON s.old_state_id = old.state_id WHERE sm.entity_id = 'switch.livingroom' AND s.state != old.state AND datetime(s.last_updated_ts, 'unixepoch', 'localtime') < '2023-11-17 08:00:00' ORDER BY s.last_updated_ts DESC LIMIT 1
    parameters:
      type: object
      properties:
        query:
          type: string
          description: A fully formed SQL query.
  function:
    type: sqlite
```

Get last changed date time of state | Get state at specific time
--|--
<img width="300" alt="스크린샷 2023-11-19 오후 5 32 56" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/5a25db59-f66c-4dfd-9e7b-ae6982ed3cd2"> |<img width="300" alt="스크린샷 2023-11-19 오후 5 32 30" src="https://github.com/jekalmin/extended_openai_conversation/assets/2917984/51faaa26-3294-4f96-b115-c71b268b708e"> 


**FAQ**
1. Can gpt modify or delete data?
    > No, since connection is created in a read only mode, data are only used for fetching. 
2. Can gpt query data that are not exposed in database?
    > Yes, it is hard to validate whether a query is only using exposed entities.
3. Query uses UTC time. Is there any way to adjust timezone?
    > Yes. Set "TZ" environment variable to your [region](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (eg. `Asia/Seoul`). <br/>
      Or use plus/minus hours to adjust instead of 'localtime' (eg. `datetime(s.last_updated_ts, 'unixepoch', '+9 hours')`).


#### 7-2. Let model generate a query (with minimum validation)
- If need to check at least "entity_id" of exposed entities is present in a query, use "is_exposed_entity_in_query" in combination with "raise".
- Not secured enough, but flexible way
```yaml
- spec:
    name: query_histories_from_db
    description: >-
      Use this function to query histories from Home Assistant SQLite database.
      Example:
        Question: When did bedroom light turn on?
        Answer: SELECT datetime(s.last_updated_ts, 'unixepoch', 'localtime') last_updated_ts FROM states s INNER JOIN states_meta sm ON s.metadata_id = sm.metadata_id INNER JOIN states old ON s.old_state_id = old.state_id WHERE sm.entity_id = 'light.bedroom' AND s.state = 'on' AND s.state != old.state ORDER BY s.last_updated_ts DESC LIMIT 1
        Question: Was livingroom light on at 9 am?
        Answer: SELECT datetime(s.last_updated_ts, 'unixepoch', 'localtime') last_updated, s.state FROM states s INNER JOIN states_meta sm ON s.metadata_id = sm.metadata_id INNER JOIN states old ON s.old_state_id = old.state_id WHERE sm.entity_id = 'switch.livingroom' AND s.state != old.state AND datetime(s.last_updated_ts, 'unixepoch', 'localtime') < '2023-11-17 08:00:00' ORDER BY s.last_updated_ts DESC LIMIT 1
    parameters:
      type: object
      properties:
        query:
          type: string
          description: A fully formed SQL query.
  function:
    type: sqlite
    query: >-
      {%- if is_exposed_entity_in_query(query) -%}
        {{ query }}
      {%- else -%}
        {{ raise("entity_id should be exposed.") }}
      {%- endif -%}
```

#### 7-3. Defined SQL manually
- Use a user defined query, which is verified. And model passes a requested entity to get data from database.
- Secured, but less flexible way
```yaml
- spec:
    name: get_last_updated_time_of_entity
    description: >
      Use this function to get last updated time of entity
    parameters:
      type: object
      properties:
        entity_id:
          type: string
          description: The target entity
  function:
    type: sqlite
    query: >-
      {%- if is_exposed(entity_id) -%}
        SELECT datetime(s.last_updated_ts, 'unixepoch', 'localtime') as last_updated_ts
        FROM states s
          INNER JOIN states_meta sm ON s.metadata_id = sm.metadata_id
          INNER JOIN states old ON s.old_state_id = old.state_id
        WHERE sm.entity_id = '{{entity_id}}' AND s.state != old.state ORDER BY s.last_updated_ts DESC LIMIT 1
      {%- else -%}
        {{ raise("entity_id should be exposed.") }}
      {%- endif -%}
```

## Practical Usage
See more practical [examples](https://github.com/jekalmin/extended_openai_conversation/tree/main/examples).

## Logging
In order to monitor logs of API requests and responses, add following config to `configuration.yaml` file

```yaml
logger:
  logs:
    custom_components.extended_openai_conversation: info
```
