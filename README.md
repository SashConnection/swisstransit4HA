# Swiss Transit For HA

<img src="https://raw.githubusercontent.com/SashConnection/swisstransit4HA/main/custom_components/swisstransit4ha/brand/icon.png" alt="Logo" width="96" align="right">

**Next departures from your Swiss stop or station in Home Assistant**, with real-time delays, cancellations, platform changes and disruption messages.
Buses, trams, trains, metro, boats and cable cars, anywhere in Switzerland. Available in **French, German, Italian and English**.

🇫🇷 [En français plus bas](#en-français)

## Features

| | |
|---|---|
| 🚏 **Any stop** | Search by name, e.g. *Lausanne, Flon*, *Bern*, *Zürich, Paradeplatz* |
| ⏱️ **Real time** | Expected time, delay in minutes, cancelled departures, platform changes |
| ⚠️ **Disruptions** | Official messages (SIRI-SX) for the lines and stop you follow |
| 🎯 **Filters** | Lines (`9, 21, S3`), direction (`Genève`), means of transport, walking time to the stop |
| 🪧 **Card** | A ready-made departure board for your dashboard |
| 🔔 **Automations** | A *Disruption* sensor turns on when a message is active, a departure is cancelled or late |

## Data sources

| | Without key | With a free key |
|---|---|---|
| Source | [transport.opendata.ch](https://transport.opendata.ch) | [opentransportdata.swiss](https://opentransportdata.swiss) (OJP 2.0) |
| Timetable | ✅ every stop | ✅ every stop |
| Real-time delays | trains, some city networks | almost every operator, buses and trams included |
| Cancellations | ❌ | ✅ |
| Disruption messages | ❌ | ✅ |

**Get a key (free, 2 minutes):** create an account on [api-manager.opentransportdata.swiss](https://api-manager.opentransportdata.swiss), create an application and subscribe it to **OJP 2.0**, then copy the key. You can add it later in the integration options.

## Installation

**HACS:** HACS → ⋮ → *Custom repositories* → `https://github.com/SashConnection/swisstransit4HA`, category *Integration* → install *Swiss Transit For HA* → restart Home Assistant.

**Manual:** copy `custom_components/swisstransit4ha` into your `config/custom_components` folder and restart.

Then: *Settings → Devices & services → Add integration → Swiss Transit For HA*. Add the integration once per stop or direction (e.g. *Lausanne → Genève* and *Lausanne → Bern*).

## Entities (per stop)

| Entity | State | Attributes |
|---|---|---|
| `sensor.<stop>_next_departure` | departure time (real time when known) | line, destination, platform, delay, cancelled |
| `sensor.<stop>_second_departure`, `_third_departure` | same | same |
| `sensor.<stop>_delay` | delay of the next departure, in minutes | |
| `sensor.<stop>_departure_board` | number of departures | `departures` and `alerts` lists, for the card and templates |
| `sensor.<stop>_alerts` | number of active messages | `alerts` |
| `binary_sensor.<stop>_disruption` | on when something goes wrong | `alerts`, `cancelled`, `delayed` |

## Card

The card is loaded automatically. In a dashboard: *Add card → Swiss Transit departures*, then pick a style in the editor:

| Style | Looks like |
|---|---|
| `list` | Clean list: line, destination, platform, time, delay, minutes left |
| `flap` | Split-flap station board: the letters spin when a departure or a delay changes |
| `platform` | Dark blue platform display with a live clock, blinking delays and a scrolling disruption banner |
| `countdown` | One big countdown to the next departure, the following ones as chips, and *leave in X min* from your walking time. Made for wall tablets |
| `timeline` | The next 30 minutes on a time axis, one row per line |

In YAML:

```yaml
type: custom:swisstransit-departures-card
entity: sensor.lausanne_flon_departure_board
style: flap          # list, flap, platform, countdown, timeline
max: 8               # optional
window: 30           # optional, timeline length in minutes
show_platform: true  # optional
show_alerts: true    # optional
title: To work       # optional
```

## Automation example

```yaml
alias: Warn me when my train is late
triggers:
  - trigger: state
    entity_id: binary_sensor.lausanne_disruption
    to: "on"
conditions:
  - condition: time
    after: "06:30:00"
    before: "08:30:00"
    weekday: [mon, tue, wed, thu, fri]
actions:
  - action: notify.mobile_app_my_phone
    data:
      title: "🚆 Disruption at Lausanne"
      message: >
        {{ (state_attr('binary_sensor.lausanne_disruption', 'alerts')
            + state_attr('binary_sensor.lausanne_disruption', 'delayed')
            + state_attr('binary_sensor.lausanne_disruption', 'cancelled')) | join(', ') }}
```

---

## En français

**Les prochains départs de ton arrêt ou de ta gare dans Home Assistant**, avec les retards en temps réel, les suppressions, les changements de voie et les messages de perturbation. Bus, trams, trains, métro, bateaux et remontées mécaniques, partout en Suisse.

**Installation :** HACS → ⋮ → *Dépôts personnalisés* → `https://github.com/SashConnection/swisstransit4HA`, catégorie *Intégration* → installer → redémarrer Home Assistant. Ensuite *Paramètres → Appareils et services → Ajouter une intégration → Swiss Transit For HA*, et tape le nom de ton arrêt.

**Clé gratuite (recommandée) :** sans clé, les données viennent de transport.opendata.ch. Le temps réel couvre surtout les trains. Avec une clé [opentransportdata.swiss](https://api-manager.opentransportdata.swiss) abonnée à **OJP 2.0**, tu as aussi le temps réel des bus et trams, les suppressions et les messages de perturbation. La clé peut être ajoutée plus tard dans les options.

**Filtres :** lignes (`9, 21, S3`), direction (`Genève`), moyens de transport, temps de marche jusqu'à l'arrêt (cache les départs que tu ne peux plus attraper).

**Carte :** *Ajouter une carte → Swiss Transit departures*, puis choisis un style dans l'éditeur : liste, tableau à palettes (les lettres tournent comme dans les gares), affichage de quai, prochain départ en grand (avec « pars dans X min ») ou frise des 30 prochaines minutes.

---

Data: [opentransportdata.swiss](https://opentransportdata.swiss) (Open Data Platform Mobility Switzerland) and [transport.opendata.ch](https://transport.opendata.ch). This project is not affiliated with SBB CFF FFS or any transport company.

MIT License
