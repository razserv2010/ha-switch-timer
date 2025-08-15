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

# Domains supported by this integration for timed actions
SUPPORTED_DOMAINS = ("switch", "light", "fan")

# Runtime state
unsub_dict = {}
switch_timer_entities_dict = {}  # maps 'switch_timer.xxx' -> 'switch'/'light'/'fan'
active_timers = {}


def _timer_suffix(timer_entity: str) -> str:
    """Return the suffix after 'switch_timer.' (length 13 incl. dot)."""
    # 'switch_timer.'.__len__() == 13
    return timer_entity[13:]


def get_source_entity(timer_entity: str):
    """
    Convert a timer entity (switch_timer.xxx) back to its source entity and type.
    Uses switch_timer_entities_dict to resolve the original domain.
    """
    src_type = switch_timer_entities_dict.get(timer_entity)
    if src_type in SUPPORTED_DOMAINS:
        return {"type": src_type, "entity": f"{src_type}.{_timer_suffix(timer_entity)}"}
    raise KeyError(f"Unsupported or unknown source type for {timer_entity}: {src_type}")


def get_switch_timer_entity(source_entity: str):
    """
    Convert a source entity (e.g., 'switch.xxx', 'light.xxx', 'fan.xxx') to timer entity.
    Returns dict {'type': <domain>, 'entity': 'switch_timer.xxx'} or None if unsupported.
    """
    for domain in SUPPORTED_DOMAINS:
        prefix = f"{domain}."
        if source_entity.startswith(prefix):
            return {"type": domain, "entity": f"{DOMAIN}{source_entity[len(domain):]}"}
    return None


async def handle_timer_entity(hass, timer_entity, action):
    """Execute the scheduled action and reset timer state."""
    global active_timers, unsub_dict
    source_entity = get_source_entity(timer_entity)

    await hass.services.async_call(
        source_entity["type"], action, {"entity_id": source_entity["entity"]}
    )

    # Clean up runtime data
    if timer_entity in unsub_dict:
        del unsub_dict[timer_entity]
    if timer_entity in active_timers:
        del active_timers[timer_entity]
        await save_data(hass, active_timers)

    # Set timer entity back to idle
    friendly = hass.states.get(source_entity["entity"]).attributes.get(
        "friendly_name", source_entity["entity"]
    )
    hass.states.async_set(
        timer_entity, "idle", {"friendly_name": f"{friendly} timer"}
    )

    # Log result
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
    """Return only timers that are still in the future."""
    unfinished_timers = {}
    for timer in saved_timers:
        timer_finishing_at = datetime.strptime(
            saved_timers[timer]["finishing_at"], "%Y-%m-%dT%H:%M:%S.%f%z"
        )
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

        # React only to supported source domains
        if not any(event_entity.startswith(f"{d}.") for d in SUPPORTED_DOMAINS):
            return None

        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        # ----- Entity added -----
        if old_state is None:
            st_entity = get_switch_timer_entity(event_entity)
            if not st_entity:
                return None

            new_entity = st_entity["entity"]  # switch_timer.xxx
            new_entity_type = st_entity["type"]  # switch/light/fan

            if new_entity not in switch_timer_entities_dict:
                switch_timer_entities_dict[new_entity] = new_entity_type

                friendly = hass.states.get(event_entity).attributes.get(
                    "friendly_name", event_entity
                )
                hass.states.async_set(
                    new_entity, "idle", {"friendly_name": f"{friendly} timer"}
                )
                _LOGGER.info(f"Entity {new_entity} created for {event_entity}")
            else:
                return None

            # Restore ongoing timer if exists
            if new_entity in saved_timers:
                new_entity_time_to_run = datetime.strptime(
                    saved_timers[new_entity]["finishing_at"], "%Y-%m-%dT%H:%M:%S.%f%z"
                )
                if saved_timers[new_entity]["corresponding_entity"] == event_entity:
                    hass.states.async_set(
                        new_entity,
                        "set",
                        {
                            "friendly_name": f"{hass.states.get(event_entity).attributes.get('friendly_name', event_entity)} timer",
                            "finishing_at": saved_timers[new_entity]["finishing_at"],
                            "duration": saved_timers[new_entity]["duration"],
                            "action": saved_timers[new_entity]["action"],
                        },
                    )
                    unsub_dict[new_entity] = async_track_point_in_time(
                        hass,
                        create_timer_callback(
                            hass, new_entity, saved_timers[new_entity]["action"]
                        ),
                        new_entity_time_to_run,
                    )
                    _LOGGER.info(
                        "Ongoing timer restored for %s entity. Device will %s at %s",
                        new_entity,
                        saved_timers[new_entity]["action"].replace("_", " "),
                        new_entity_time_to_run.astimezone(user_timezone).strftime(
                            "%H:%M"
                        ),
                    )

        # ----- Entity removed -----
        if new_state is None:
            st_entity = get_switch_timer_entity(event_entity)
            if not st_entity:
                return None

            timer_entity_id = st_entity["entity"]  # 'switch_timer.xxx'

            # Cancel scheduled callback if exists
            if timer_entity_id in unsub_dict:
                unsub_dict[timer_entity_id]()
                del unsub_dict[timer_entity_id]

            # Remove from active_timers and persist
            if timer_entity_id in active_timers:
                del active_timers[timer_entity_id]
                await save_data(hass, active_timers)

            # Remove HA state + mapping
            hass.states.async_set(timer_entity_id, None)
            if timer_entity_id in switch_timer_entities_dict:
                del switch_timer_entities_dict[timer_entity_id]

            _LOGGER.info(
                "Entity %s removed. Source entity %s no longer present",
                timer_entity_id,
                event_entity,
            )

    hass.bus.async_listen("state_changed", entity_state_change_handler)

    # ------------------ Validators ------------------

    def validate_duration(value):
        pattern = r"^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$"
        match = fullmatch(pattern, value.strip())

        if not match:
            raise vol.Invalid(
                "Invalid duration specified. Provide timer duration in HH:MM:SS format"
            )

        return match[0]

    def validate_action(value):
        if value == "Turn on":
            value = "turn_on"
        elif value == "Turn off":
            value = "turn_off"
        elif value == "Toggle":
            value = "toggle"

        if value not in ("turn_on", "turn_off", "toggle"):
            raise vol.Invalid(
                "Invalid action value specified. Supported values: 'turn_on', 'turn_off', 'toggle'"
            )
        return value

    def validate_set_timer_entity(value):
        if not value.startswith(DOMAIN + "."):
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

    # ------------------ Services ------------------

    set_timer_schema = vol.Schema(
        {
            vol.Required("entity_id"): validate_set_timer_entity,
            vol.Required("action"): validate_action,
            vol.Required("duration"): validate_duration,
        }
    )

    cancel_timer_schema = vol.Schema({vol.Required("entity_id"): validate_cancel_timer_entity})

    async def set_timer_handler(call):
        global unsub_dict, active_timers
        data = dict(call.data)

        try:
            validated_data = set_timer_schema(data)
        except vol.Invalid as error:
            raise HomeAssistantError(f"Invalid service data: {error}")

        timer_entity = validated_data["entity_id"]
        passed_time = datetime.strptime(validated_data["duration"], "%H:%M:%S").time()
        time_to_run = datetime.now(timezone.utc) + timedelta(
            hours=passed_time.hour, minutes=passed_time.minute, seconds=passed_time.second
        )

        source = get_source_entity(timer_entity)["entity"]
        friendly = hass.states.get(source).attributes.get("friendly_name", source)

        hass.states.async_set(
            timer_entity,
            "set",
            {
                "friendly_name": f"{friendly} timer",
                "finishing_at": time_to_run.strftime("%Y-%m-%dT%H:%M:%S.%f%z"),
                "duration": validated_data["duration"],
                "action": validated_data["action"],
            },
        )
        unsub_dict[timer_entity] = async_track_point_in_time(
            hass, create_timer_callback(hass, timer_entity, validated_data["action"]), time_to_run
        )

        active_timers[timer_entity] = {
            "finishing_at": time_to_run.strftime("%Y-%m-%dT%H:%M:%S.%f%z"),
            "corresponding_entity": source,
            "duration": validated_data["duration"],
            "action": validated_data["action"],
        }
        await save_data(hass, active_timers)

        _LOGGER.info(
            "Timer set for %s entity. Device will %s at %s",
            timer_entity,
            validated_data["action"].replace("_", " "),
            time_to_run.astimezone(user_timezone).strftime("%H:%M"),
        )

    async def cancel_timer_handler(call):
        global unsub_dict, active_timers

        data = dict(call.data)
        try:
            validated_data = cancel_timer_schema(data)
        except vol.Invalid as error:
            raise HomeAssistantError(error)
        else:
            timer_entity = validated_data["entity_id"]
            corresponding_entity = get_source_entity(timer_entity)["entity"]

            if timer_entity in unsub_dict:
                unsub_dict[timer_entity]()
                del unsub_dict[timer_entity]

            if timer_entity in active_timers:
                del active_timers[timer_entity]
                await save_data(hass, active_timers)

            friendly = hass.states.get(corresponding_entity).attributes.get(
                "friendly_name", corresponding_entity
            )
            hass.states.async_set(
                timer_entity, "idle", {"friendly_name": f"{friendly} timer"}
            )
            _LOGGER.info("Timer canceled for %s", timer_entity)

    hass.services.async_register(DOMAIN, "set_timer", set_timer_handler)
    hass.services.async_register(DOMAIN, "cancel_timer", cancel_timer_handler)

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
