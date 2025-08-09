import logging
from homeassistant.helpers.event import async_track_point_in_time
from datetime import datetime, timedelta, timezone
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from zoneinfo import ZoneInfo
from re import fullmatch
import voluptuous as vol



_LOGGER = logging.getLogger(__package__)
DOMAIN = "switch_timer"

unsub_dict = {}
switch_timer_entities_dict = {}
active_timers = {}



def get_source_entity(timer_entity):
    if switch_timer_entities_dict[timer_entity] == "switch":
        return {"type": "switch", "entity": "switch."+timer_entity[13:]}
    elif switch_timer_entities_dict[timer_entity] == "light":
        return {"type": "light", "entity": "light."+timer_entity[13:]}


def get_switch_timer_entity(source_entity):
    if source_entity.startswith("switch."):
        return {"type": "switch", "entity": DOMAIN+source_entity[6:]}
    elif source_entity.startswith("light."):
        return {"type": "light", "entity": DOMAIN+source_entity[5:]}
        

async def handle_timer_entity(hass, timer_entity, action):
    global active_timers, unsub_dict
    source_entity = get_source_entity(timer_entity)
    await hass.services.async_call(source_entity["type"], action, {"entity_id": source_entity["entity"]})
    del unsub_dict[timer_entity]
    del active_timers[timer_entity]
    await save_data(hass, active_timers)
    hass.states.async_set(timer_entity, "idle", {"friendly_name": hass.states.get(source_entity["entity"]).attributes.get("friendly_name")+" timer"})
    log_string = ""
    if action == "turn_off":
        log_string = "Device turned off"
    elif action == "turn_on":
        log_string = "Device turned on"
    elif action == "toggle":
        new_state = hass.states.get(source_entity["entity"]).state
        log_string = f"Device turned {new_state}"
    _LOGGER.info(f"Timer duration over on {timer_entity}. {log_string}")


def create_timer_callback(hass, timer_entity, action):
    async def _callback(_now):
        await handle_timer_entity(hass, timer_entity, action)
    return _callback



async def get_unfinished_timers(hass, saved_timers):
    unfinished_timers = {}
    for timer in saved_timers:
        timer_finishing_at = datetime.strptime(saved_timers[timer]["finishing_at"], "%Y-%m-%dT%H:%M:%S.%f%z")
        if timer_finishing_at > datetime.now(timezone.utc):
            unfinished_timers[timer] = saved_timers[timer]
    return unfinished_timers


async def async_setup(hass, config):
    global active_timers, unsub_dict, user_timezone
    stored_timers = await load_data(hass)
    saved_timers = await get_unfinished_timers(hass, stored_timers)
    await save_data(hass, saved_timers)
    active_timers = saved_timers
    user_timezone = ZoneInfo(hass.config.time_zone)

    async def entity_state_change_handler(event):
        event_entity = event.data.get("entity_id")

        if event_entity.startswith("switch.") or event_entity.startswith("light."):    
            old_state = event.data.get("old_state")
            new_state = event.data.get("new_state")

            if old_state == None: # If a new switch or light entity gets added to the system
                new_entity = get_switch_timer_entity(event_entity)["entity"]
                new_entity_type = get_switch_timer_entity(event_entity)["type"]


                if new_entity not in list(switch_timer_entities_dict.keys()):
                    switch_timer_entities_dict[new_entity] = new_entity_type
                    hass.states.async_set(new_entity, "idle", {"friendly_name": hass.states.get(event_entity).attributes.get("friendly_name")+" timer"})
                    _LOGGER.info(f"Entity {new_entity} created for {event_entity}")
                else:
                    return None

                if new_entity in list(saved_timers.keys()): # If there is a saved timer in the storage file for the entity
                    new_entity_time_to_run = datetime.strptime(saved_timers[new_entity]["finishing_at"], "%Y-%m-%dT%H:%M:%S.%f%z")
                    if saved_timers[new_entity]["corresponding_entity"] == event_entity:
                        hass.states.async_set(new_entity, "set", {"friendly_name": hass.states.get(event_entity).attributes.get("friendly_name")+" timer", "finishing_at": saved_timers[new_entity]["finishing_at"], "duration": saved_timers[new_entity]["duration"], "action": saved_timers[new_entity]["action"]})
                        unsub_dict[new_entity] = async_track_point_in_time(hass, create_timer_callback(hass, new_entity, saved_timers[new_entity]["action"]), new_entity_time_to_run)
                        _LOGGER.info(f"Ongoing timer restored for {new_entity} entity. Device will {saved_timers[new_entity]["action"].replace("_", " ")} at {new_entity_time_to_run.astimezone(user_timezone).strftime("%H:%M")}")


            if new_state == None: # If a switch or a light entity gets removed
                switch_timer_entity = get_switch_timer_entity(event_entity)

                if switch_timer_entity in list(unsub_dict.keys()):
                    unsub_dict[switch_timer_entity]()
                    del unsub_dict[switch_timer_entity]
                    del active_timers[switch_timer_entity]
                    save_data(hass, active_timers)

                hass.states.async_set(switch_timer_entity["entity"], None)
                del switch_timer_entities_dict[switch_timer_entity["entity"]]
                
                _LOGGER.info(f"Entity {switch_timer_entity["entity"]} removed. Source entity {event_entity} no longer present")

    hass.bus.async_listen("state_changed", entity_state_change_handler)


    def validate_duration(value):
        pattern = r"^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$"
        match = fullmatch(pattern, value.strip())

        if not match:
            raise vol.Invalid("Invalid duration specified. Provide timer duration in HH:MM:SS format")

        return match[0]


    def validate_action(value):
        if value == "Turn on":
            value = "turn_on"
        elif value == "Turn off":
            value = "turn_off"
        elif value == "Toggle":
            value = "toggle"

        if value not in ("turn_on", "turn_off", "toggle"):
            raise vol.Invalid("Invalid action value specified. Supported values: 'turn_on', 'turn_off', 'toggle'")
        return value


    def validate_set_timer_entity(value):
        if not value.startswith(DOMAIN+"."):
            raise vol.Invalid("Invalid entity specified")
        elif value not in hass.states.async_entity_ids():
            raise vol.Invalid("Entity doesn't exsist")
        return value


    def validate_cancel_timer_entity(value):
        if value not in hass.states.async_entity_ids():
            raise vol.Invalid(f"Entity {value} doesn't exsist")
        elif value not in unsub_dict.keys():
            raise vol.Invalid(f"Timer not set for {value} entity")
        return value



    set_timer_schema = vol.Schema({
        vol.Required('entity_id'): validate_set_timer_entity,
        vol.Required('action'): validate_action,
        vol.Required('duration'): validate_duration,
    })

    cancel_timer_schema = vol.Schema({
        vol.Required('entity_id'): validate_cancel_timer_entity
    })



    async def set_timer_handler(call):
        global unsub_dict, active_timers
        data = dict(call.data)

        try:
            validated_data = set_timer_schema(data)
        except vol.Invalid as error:
            raise HomeAssistantError(f"Invalid service data: {error}")

        timer_entity = validated_data['entity_id']
        passed_time = datetime.strptime(validated_data['duration'], "%H:%M:%S").time()
        time_to_run = datetime.now(timezone.utc) + timedelta(hours=passed_time.hour, minutes=passed_time.minute, seconds=passed_time.second)
        hass.states.async_set(timer_entity, "set", {"friendly_name": hass.states.get(get_source_entity(timer_entity)["entity"]).attributes.get("friendly_name")+" timer", "finishing_at": time_to_run.strftime('%Y-%m-%dT%H:%M:%S.%f%z'), "duration": validated_data['duration'], "action": validated_data['action']})
        unsub_dict[timer_entity] = async_track_point_in_time(hass, create_timer_callback(hass, timer_entity, validated_data['action']), time_to_run)

        active_timers[timer_entity] = {"finishing_at": time_to_run.strftime('%Y-%m-%dT%H:%M:%S.%f%z'), "corresponding_entity": get_source_entity(timer_entity)["entity"], "duration": validated_data['duration'], "action": validated_data['action']}
        await save_data(hass, active_timers)

        _LOGGER.info(f"Timer set for {timer_entity} entity. Device will {validated_data["action"].replace("_", " ")} at {time_to_run.astimezone(user_timezone).strftime("%H:%M")}")


    async def cancel_timer_handler(call):
        global unsub_dict, active_timers

        data = dict(call.data)
        try:
            validated_data = cancel_timer_schema(data)
        except vol.Invalid as error:
            raise HomeAssistantError(error)
        else:
            timer_entity = validated_data['entity_id']
            corresponding_entity = get_source_entity(timer_entity)["entity"]

            unsub_dict[timer_entity]()
            del unsub_dict[timer_entity]
            del active_timers[timer_entity]
            await save_data(hass, active_timers)
            hass.states.async_set(timer_entity, "idle", {"friendly_name": hass.states.get(corresponding_entity).attributes.get("friendly_name")+" timer"})
            _LOGGER.info(f"Timer canceled for {timer_entity}")
        

    hass.services.async_register(DOMAIN, 'set_timer', set_timer_handler)
    hass.services.async_register(DOMAIN, 'cancel_timer', cancel_timer_handler)

    _LOGGER.info("Integration loaded")
    return True


async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_unload_entry(hass, entry):
    hass.data[DOMAIN].pop(entry.entry_id)
    return True


async def save_data(hass, data):
    store = Store(hass, 1, f"{DOMAIN}.json")
    await store.async_save(data)


async def load_data(hass):
    store = Store(hass, 1, f"{DOMAIN}.json")
    data = await store.async_load()
    return data if data else {}
