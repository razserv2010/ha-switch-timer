import logging
from homeassistant import config_entries


_LOGGER = logging.getLogger(__package__)
DOMAIN = "switch_timer"


@config_entries.HANDLERS.register(DOMAIN)
class SwitchTimerConfigFlow(config_entries.ConfigFlow):

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        return self.async_create_entry(title="Switch timer", data={})