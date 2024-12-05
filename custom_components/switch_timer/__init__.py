import logging
from homeassistant.helpers.event import track_time_interval, async_track_point_in_time
from datetime import datetime, timedelta, timezone
from homeassistant.exceptions import HomeAssistantError
import voluptuous as vol


_LOGGER = logging.getLogger(__package__)
DOMAIN = "switch_timer"

unsub_dict = {}



def setup(hass, config):

    def get_switch_entites():
        all_entities = hass.states.async_entity_ids()
        switch_entities = []

        for entity in all_entities:
            if entity.startswith("switch."):
                switch_entities.append(entity)
        
        return switch_entities
    

    def add_timer_entities(switch_entities):
        entities = []
        for entity in switch_entities:
            entity_device_name = entity[7:]
            new_entity_name = DOMAIN + "." + entity_device_name
            
            if new_entity_name not in hass.states.async_entity_ids():
                hass.states.set(new_entity_name, "idle")
        

    add_timer_entities(get_switch_entites())


    def update_switch_entities(call):
        _LOGGER.info("Updating timer entities")
        add_timer_entities(get_switch_entites())

    track_time_interval(hass, update_switch_entities, timedelta(seconds=10))


    def validate_duration(value):
        try:
            entered_datetime =  datetime.strptime(value, "%H:%M:%S")
        except ValueError:
            raise vol.Invalid("Invalid duration specified. Provide timer duration in HH:MM:SS format")
        else:
            if entered_datetime == datetime(1900, 1, 1, 0, 0):
                raise vol.Invalid("Timer durration can't be none")
        return value


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


    def handle_timer_entity(timer_entity, action):
        switch_entity = "switch."+timer_entity[13:]
        _LOGGER.info(f"Timer duration over on {timer_entity}")

        hass.services.call("switch", action, {"entity_id": switch_entity})
        hass.states.set(timer_entity, "idle")


    def set_timer_handler(call):
        global unsub_dict
        data = dict(call.data)

        try:
            validated_data = set_timer_schema(data)
        except vol.Invalid as error:
            raise HomeAssistantError(f"Invalid service data: {error}")


        timer_entity = validated_data['entity_id']
        passed_time = datetime.strptime(validated_data['duration'], "%H:%M:%S").time()
        time_to_run = datetime.now(timezone.utc) + timedelta(hours=passed_time.hour, minutes=passed_time.minute, seconds=passed_time.second)
        hass.states.set(timer_entity, "set", {"finishing_at": time_to_run.strftime('%Y-%m-%dT%H:%M:%S.%f%z'), "duration": validated_data['duration'], "action": validated_data['action']})
        unsub_dict[timer_entity] = async_track_point_in_time(hass, lambda call: handle_timer_entity(timer_entity, validated_data['action']), time_to_run)
        _LOGGER.info(f"Timer set for {timer_entity} entity. Duration: {validated_data['duration']}, Action: {validated_data['action']}")


    
    def cancel_timer_handler(call):
        global unsub_dict

        data = dict(call.data)
        try:
            validated_data = cancel_timer_schema(data)
        except vol.Invalid as error:
            raise HomeAssistantError(error)


        timer_entity = validated_data['entity_id']
        hass.states.set(timer_entity, "idle")
        unsub_dict[timer_entity]()
        unsub_dict.pop(timer_entity)
        _LOGGER.info(f"Timer canceled for {timer_entity}")
        
    
    hass.services.register(DOMAIN, 'set_timer', set_timer_handler)
    hass.services.register(DOMAIN, 'cancel_timer', cancel_timer_handler)

    _LOGGER.info("Setup completed")
    return True


async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_unload_entry(hass, entry):
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
