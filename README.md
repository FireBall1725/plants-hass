# Plants

A Home Assistant integration that turns a soil sensor into a plant: one device per plant, with its own moisture band, a watering detector that ignores morning dew, and cards to show it all.

Before this, a plant was a pile of helpers: a smoothing filter, a statistics window, a floor and ceiling, a last-watered date and button, a few template sensors, and a branch of an automation. Plants replaces all of that with one config entry per plant, made by picking the sensor device.

## Install

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=FireBall1725&repository=plants-hass&category=integration)

Add this repository to HACS as a custom repository of type Integration, install it, and restart Home Assistant. Then go to Settings, Devices and services, Add integration, and pick Plants.

## Adding a plant

Pick the plant's sensor device (a Mi Flora or anything else with a soil moisture sensor). Plants finds the moisture, temperature, light, conductivity and battery sensors on that device by their device class, so there's nothing to map by hand.

Then choose a profile. It sets the starting moisture band and how big a rise counts as watering:

| Profile | Floor | Ceiling | Rise that counts as watering |
|---|---|---|---|
| Succulent | 8% | 30% | 6 points |
| Herb | 25% | 60% | 10 points |
| Tropical | 20% | 50% | 10 points |
| Custom | 15% | 60% | 10 points |

The floor and ceiling are number entities on the plant, so you can move them from the dashboard later. Everything else is under Configure.

## What each plant gets

- `sensor.<plant>_status`: ok, water soon, dry, stale (no reading for two hours) or check probe (the probe reads zero, which a probe in soil doesn't do)
- `sensor.<plant>_last_watered`, with the pending watering as attributes while it's being confirmed
- `sensor.<plant>_moisture_trend`, in points per day over the last three days
- `sensor.<plant>_reaches_floor`, when the trend says it'll hit the floor
- `binary_sensor.<plant>_needs_water`
- `number.<plant>_moisture_floor` and `number.<plant>_moisture_ceiling`
- `button.<plant>_watered`, for when you water and don't want to wait for the detector

## How watering is detected

A dry pot's reading swings with the day. A jade at 3% overnight can read 6% at nine in the morning and be back to 3% by noon, and a rule that fires on any rise will log a watering every morning.

The detector smooths the readings over 15 minutes, looks for a rise of at least the profile's threshold within 12 hours, and only confirms it if the rise is still there six hours later. Dew is gone by then; water isn't. The watering is stamped at the start of the rise, not at confirmation, and a press of the Watered button counts the same water once, not twice.

## Icons

Each plant has a mark, used on the cards and on a FireLabs plant display: succulent, herb, seedling, cactus, fern, flowering or tropical leaf. You can also upload your own image under Configure. A PNG with a transparent background works best. A drawing on a plain background works too. It's turned into a one-colour mark that takes the status colour.

## Cards

The cards ship with the integration and load by themselves, so there's no resource to add.

One plant: the moisture reading, its trend, and a seven-day curve with the floor drawn in.

```yaml
type: custom:plants-card
plant: Jade
```

`plant` takes the plant's name or its config entry id. The card editor lists your plants.

Every plant, sorted by who needs water first, each against its own floor:

```yaml
type: custom:plants-triage-card
```

Daily peak light for every plant over the last ten days, one line each. Sensors on the same windowsill should trace each other, so a line that wanders off on its own points at the sensor, not the room. When every plant drops at once and stays down, the card marks the day it started; that usually means the plants moved or something now shades them.

```yaml
type: custom:plants-light-card
days: 10
```

Every sensor's battery beside the last time it reported anything. Battery values change rarely, so the last-contact time is the one that tells you a sensor has gone quiet.

```yaml
type: custom:plants-battery-card
```

## For other integrations

Two websocket commands carry everything the cards use:

- `plants/list` returns every plant: readings with their age, band, status, trend, last watered, and the icon.
- `plants/history` returns hourly mean moisture per plant, seven days by default (`hours` goes up to 744). `reading` picks another sensor, and `period: day` with `stat: max` and `days` gives daily peaks, which is what the light card uses.

The FireLabs plant display reads plants the same way.

## Support

Questions, updates, and works in progress: [FireBall Codes on Discord](https://discord.gg/QpV82CFfVD).

If this saved you some time, you can [buy me a sushi roll](https://ko-fi.com/fireball1725).

## Licence

AGPL-3.0-only. Copyright (C) 2026 FireBall1725.
