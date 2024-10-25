# Switch Timer
A home assistant integration for controlling switch entites by using a timer. Each individual switch entity can be set to turn on, turn off, or toggle after a specified period of time.


## Installation

### Using [HACS](https://hacs.xyz)
1. Go to the main screen of HACS and select the custom repository option in the top right conner
	<p>
	    <img src="https://i.imgur.com/HKS3sNr.png" width="500px"/>
	</p>
2. Enter the URL of this repository, select type as integration and click add
	<p>
	    <img src="https://i.imgur.com/DFRoFGJ.png" width="250px"/>
	</p>
3. Search for switch timer in HACS and download the first integration from the list
	<p>
	    <img src="https://i.imgur.com/TcBjNC6.png" />
	</p>
4. Go to integrations page in settings or use the button below and add the Switch Timer integration
	[![Setup Switch Timer](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=switch_timer)
	<p>
	    <img src=" https://i.imgur.com/VH50aBc.png" width="450px" />
		<img src="https://i.imgur.com/MvSW62k.png" width="350px"/>
	</p>

### Manual

1. Copy `custom_components/switch_timer` from this repository into your home assistant installations `custom_components/` directory.
2. Restart Home Assistant
3. Add Switch Timer integration in settings.


##  Entities & services
Integration creates switch timer entity for every switch entity in the home assistant instance. Switch timer entities are assigned to ``switch_timer`` domain, the entity name remains the same as original switch entity. As for example, ``switch.kitchen_light`` => ``switch_timer.kitchen_light``. The integration scans for new switch entities every 10 seconds, if a new switch entity is found, a switch timer entity is created for it automatically. A switch timer entity state can be either set or idle. An entity changes its state from idle to set when a timer is scheduled. Note that all scheduled timers are dropped upon a system restart, will change this in a future release. The integration provides two services for both scheduling and canceling timers. A set switch timer entity has the following attributes,
* `finishing_at` Shows the UTC timestamp when timer is scheduled to run
* `duration` Duration of the timer in HH:MM:SS format
* `action` State scheduled for the corresponding switch entity to be set to. Possible values, 'turn_on', 'turn_off, 'toggle'
	<p>
	   <img src="https://i.imgur.com/RaT6wcQ.png"/>
	</p>

<br></br>

### switch_timer.set_timer

Service used for scheduling a timer. Maximum timer duration supported is 23:59:59. Required parameters are, 
* `entity_id`  switch timer entity to set the timer for
* `action` state action to be set on the corresponding switch entity
* `duration` duration for the timer in HH:MM:SS format
```
action: switch_timer.set_timer
data:
  entity_id: switch_timer.kitchen_light
  action: "turn_off"
  duration: "00:10:00"
```
Example service call on `switch_timer.kitchen_light` entity to turn the device off after 10 minutes.

<br></br>

### switch_timer.cancel_timer

Service used for canceling a scheduled timer. The `entity_id` for the timer to be canceled is required.
```
action: switch_timer.cancel_timer
data:
  entity_id: switch_timer.kitchen_light
```
Example service call to cancel the timer scheduled on `switch_timer.kitchen_light` entity.

Both services have a GUI support implemented in developer tools section.


## Frontend usage

### [Set timer popup card](https://github.com/gh0stblizz4rd/set-timer-popup-card)
In order to easily set timers for devices straight from the dashboard, I've created [set timer popup](https://github.com/gh0stblizz4rd/set-timer-popup-card) card, which can be displayed in a [browser mod](https://github.com/thomasloven/hass-browser_mod) popup as a hold action on a card, for example.

<p>
    <img src="https://i.imgur.com/s3wWdru.png" width="500px"/>
</p>



## Upcoming features
* Save timer states upon a restart

## Issues & support
If you encounter any problems while using the integration, feel free to contact me by email romansa772@aol.com or open an issue in this repository. If you wish to support my work you can make a donation [here](https://paypal.me/romansaudzeris?country.x=LV&locale.x=en_US) or just give this repo a star.
