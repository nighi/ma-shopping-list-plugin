# Shopping list for Music Assistant 🛒🎧

A [Music Assistant](https://music-assistant.io) plugin that reads out and ticks off your
[Home Assistant](https://www.home-assistant.io) shopping list with the buttons of your headphones,
while you are in a supermarket. The music keeps playing.

| Headphones (e.g. AirPods)  | Normally       | In a supermarket zone                                      |
|----------------------------|----------------|------------------------------------------------------------|
| press once (play/pause)    | pause          | the current entry is read out over the music               |
| press twice (next)         | next track     | the entry is ticked off (or deleted), the next one is read |
| press three times (previous) | previous track | the entry moves to the end of the list                   |

Outside the zones your buttons work as usual, unless you start shopping mode by hand.

## How it works

- Shopping mode is on while a Home Assistant **person** is in one of the chosen **zones**, or
  while you started it **by hand** (see below).
- The entries come from a Home Assistant **to-do list** (`todo.get_items`) and are ticked off with
  `todo.update_item` (or deleted with `todo.remove_item`).
- Entries are spoken as **announcements** on your player, over the music.
- All of this goes through the connection of Music Assistant's own
  [Home Assistant plugin](https://music-assistant.io/ha-plugin/). The plugin talks to nothing else.

### Button presses (current limitation)

Music Assistant has no way yet for a plugin to take over the buttons of a player. The plugin
therefore watches what a press did to the player's queue and undoes it:

- **pause:** playback is resumed right away and the entry is read. You hear a short gap. Some
  players cannot pause (Music Assistant then stops them), so for them a stop in the middle of a
  track counts as this press as well.
- **next / previous:** the queue goes back to the track and position it was at, and the entry is
  ticked off or skipped. You may hear a short jump.

On a player that cannot speak over the music (Music Assistant then stops the music for an
announcement), the music is halted once, the entry is said and the music goes on where it was:
switching back and forth between music and announcement more often made such players lose words.

Two and three presses can only be seen when they move the queue: keep something after the
current track, such as a playlist, **repeat** or **Don't stop the music**. On the last track of a
queue without repeat, next does nothing, so there is nothing to see.

A track that ends by itself is not taken for a press. Any pause, next or previous on that player
while you are in the zone counts, also one from the app.

A proper way for plugins to handle player buttons would remove the gap. That needs a change in
Music Assistant itself, which is to be discussed with its maintainers.

## The page

The plugin has a page of its own, in the main menu of the Music Assistant app under
**Shopping list**, in the colours, theme and language you chose in the app: it shows the list and whether shopping mode is on, starts and ends shopping
mode, reads the current entry, ticks entries off and moves the current one to the end.

## Several people and several shops

- **One player per person:** add the plugin once per person, each with their own person and
  player (their phone). Give each a name in its settings to tell them apart.
- **A list per zone:** after choosing the zones and saving, each zone gets a setting
  *Shopping list in …*, such as a drugstore list for the drugstore. Zones left empty use the
  shopping list of the plugin, and so does shopping mode started by hand outside of the zones.

## Players

The official [Music Assistant app](https://github.com/music-assistant/mobile-app) works well.
MassDroid keeps an announcement silent right after a pause on the headphones: turn on
*Player stays silent after a pause on the headphones* (advanced settings) for it, which makes
reading out a few seconds slower.

## Requirements

- Music Assistant with the **Home Assistant plugin** set up.
- In Home Assistant: a **person** with location tracking (e.g. the Companion app), one or more
  **zones** for your supermarkets, and a **to-do list** (the built-in Shopping list is
  `todo.shopping_list`).
- A **text-to-speech engine for announcements** in Music Assistant (Settings → Players →
  Announcements). The Home Assistant plugin offers the TTS services of Home Assistant, such as
  Google Translate or Piper.
- A player that supports **announcements** and that your headphone buttons control, such as your
  phone in the [Music Assistant app](https://github.com/music-assistant/mobile-app).

## Setup

1. In Music Assistant, open **Settings → Plugins → Add** and choose **Shopping list**.
2. Fill in. The Home Assistant entities are offered to choose from; while Home Assistant is not
   reachable, entity ids can be typed instead.
   - **Player:** the player your headphones are connected to (your phone).
   - **Person:** e.g. `person.alex`. Person and zones are only needed to start shopping mode by
     location.
   - **Supermarket zones:** one or more zones, e.g. `zone.supermarket` and `zone.market`.
   - **Switch for shopping mode:** optional, e.g. `input_boolean.shopping_mode`.
   - **Shopping list:** e.g. `todo.shopping_list`.
   - **Delete entries instead of ticking them off:** off by default.
   - **Language of the announcements:** German or English.

## Starting shopping mode by hand

Shopping mode can also be on outside of the zones, for example in a shop you have no zone for:

- **The page of the plugin:** *Start shopping mode* and *End shopping mode*. Without a switch
  (below), shopping mode started this way ends when the plugin restarts, also after saving its
  settings.
- **A switch in Home Assistant** (optional): create a toggle helper, such as
  `input_boolean.shopping_mode` (*Settings → Devices & services → Helpers → Create helper →
  Toggle*), and enter it as *Switch for shopping mode*. While it is on, shopping mode is on. Switch
  it from a dashboard, a phone widget, by voice or from an automation; the page
  switches it too, and it survives restarts.

Leaving a zone does not end shopping mode that was started by hand.

Shopping mode does not start for an empty list, and a press when nothing is left ends it.
When the last entry is ticked off, shopping mode ends: one started by hand goes off (with its
switch), and a zone starts it again only after you have left it.

## Development

Based on the
[community provider template](https://github.com/music-assistant/community-provider-template).
With [uv](https://docs.astral.sh/uv/):

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run codespell
```

To try it against a real server, run the development image with this repository as provider
repository:

```sh
docker run --rm --network host -v ma-dev-data:/data \
  -e PROVIDER_REPO=nighi/ma-shopping-list-plugin \
  ghcr.io/music-assistant/server:dev
```

| File | What it does |
|---|---|
| `shopping_list/__init__.py` | The plugin: settings, zone tracking, reacting to presses, announcements |
| `shopping_list/gestures.py` | Recognises button presses from queue changes (no server needed, unit tested) |
| `shopping_list/shopping.py` | The list in the order it is walked through |
| `shopping_list/home_assistant.py` | Zone states and the to-do calls to Home Assistant |
| `shopping_list/phrases.py` | What is said, in German and English |

## Licence

Apache-2.0
