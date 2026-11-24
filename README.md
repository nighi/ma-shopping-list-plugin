# Shopping list for Music Assistant 🛒🎧

A [Music Assistant](https://music-assistant.io) plugin that reads out and ticks off your
[Home Assistant](https://www.home-assistant.io) shopping list with the buttons of your headphones,
while you are in a supermarket. The music keeps playing.

| Headphones (e.g. AirPods)  | Normally       | In a supermarket zone                                      |
|----------------------------|----------------|------------------------------------------------------------|
| press once (play/pause)    | pause          | the current entry is read out over the music               |
| press twice (next)         | next track     | the entry is ticked off (or deleted), the next one is read |
| press three times (previous) | previous track | the entry moves to the end of the list                   |

Outside the zones your buttons work as usual.

## How it works

- Shopping mode is on while a Home Assistant **person** is in one of the chosen **zones**.
- The entries come from a Home Assistant **to-do list** (`todo.get_items`) and are ticked off with
  `todo.update_item` (or deleted with `todo.remove_item`).
- Entries are spoken as **announcements** on your player, over the music.
- All of this goes through the connection of Music Assistant's own
  [Home Assistant plugin](https://music-assistant.io/ha-plugin/). The plugin talks to nothing else.

### Button presses (current limitation)

Music Assistant has no way yet for a plugin to take over the buttons of a player. The plugin
therefore watches what a press did to the player's queue and undoes it:

- **pause:** playback is resumed right away and the entry is read. You hear a short gap.
- **next / previous:** the queue goes back to the track and position it was at, and the entry is
  ticked off or skipped. You may hear a short jump.

A track that ends by itself is not taken for a press. Any pause, next or previous on that player
while you are in the zone counts, also one from the app.

A proper way for plugins to handle player buttons would remove the gap. That needs a change in
Music Assistant itself, which is to be discussed with its maintainers.

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
2. Fill in:
   - **Player:** the player your headphones are connected to (your phone).
   - **Person:** e.g. `person.alex`.
   - **Supermarket zones:** e.g. `zone.supermarket, zone.market`.
   - **Shopping list:** e.g. `todo.shopping_list`.
   - **Delete entries instead of ticking them off:** off by default.
   - **Language of the announcements:** German or English.

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
