from homeassistant.helpers.entity import Entity

class TimerEntity(Entity):

    should_poll = False

    def __init__(self, name):
        self._name = name
        self._state = "idle"
        self._attributes = {}

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    async def async_update_state(self, new_state, attributes=None, clear_attributes=False):
        self._state = new_state
        if attributes:
            self._attributes.update(attributes)
        elif clear_attributes:
            self._attributes = {}
        self.async_write_ha_state()