# Switch Timer

> **Note:** This project is a **fork** of the original [Switch Timer](https://github.com/gh0stblizz4rd/ha-switch-timer) integration by **gh0stblizz4rd**.  
> All credit for the original idea and implementation goes to the original author.  
> **This fork only adds support for the `fan` domain** in addition to `switch` and `light`.

A Home Assistant integration for controlling switch, light, and **fan** entities by using a timer. Each individual entity can be set to turn on, turn off, or toggle after a specified period of time.

---

## Installation

### Using [HACS](https://hacs.xyz)
1. Go to the main screen of HACS and select the **Custom repositories** option in the top right corner.
	<p>
	    <img src="https://i.imgur.com/HKS3sNr.png" width="500px"/>
	</p>
2. Enter the URL of this repository, select type as **Integration** and click **Add**.
	<p>
	    <img src="https://i.imgur.com/DFRoFGJ.png" width="250px"/>
	</p>
3. Search for **Switch Timer** in HACS and download the first integration from the list.
	<p>
	    <img src="https://i.imgur.com/TcBjNC6.png" />
	</p>
4. Go to the integrations page in Settings or use the button below to add the Switch Timer integration:  
	[![Setup Switch Timer](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=switch_timer)
	<p>
	    <img src=" https://i.imgur.com/VH50aBc.png" width="450px" />
		<img src="https://i.imgur.com/MvSW62k.png" width="350px"/>
	</p>

### Manual

1. Copy `custom_components/switch_timer` from this repository into your Home Assistant installation’s `custom_components/` directory.
2. Restart Home Assistant.
3. Add the Switch Timer integration in Settings.

---

## Entities & Services
This integration creates a `switch_timer` entity for every **switch**, **light**, or **fan** entity in the Home Assistant instance.  
The timer entity name remains the same as the original entity name, for example:  
- `switch.kitchen_light` → `switch_timer.kitchen_light`  
- `fan.living_room_fan` → `switch_timer.living_room_fan`

The integration scans for new supported entities every 10 seconds.  
A timer entity state can be:
- `idle` — no timer is set  
- `set` — a timer is scheduled

A set timer entity has the following attributes:
* `finishing_at` — UTC timestamp when the timer will run
* `duration` — Timer length in `HH:MM:SS` format
* `action` — Scheduled action: `turn_on`, `turn_off`, or `toggle`

<p>
   <img src="https://i.imgur.com/RaT6wcQ.png"/>
</p>

---

### `switch_timer.set_timer`

Schedules a timer.  
**Max duration:** `23:59:59`  

**Parameters:**
* `entity_id` — Timer entity to control
* `action` — `turn_on`, `turn_off`, or `toggle`
* `duration` — in `HH:MM:SS` format

```yaml
action: switch_timer.set_timer
data:
  entity_id: switch_timer.kitchen_light
  action: "turn_off"
  duration: "00:10:00"
