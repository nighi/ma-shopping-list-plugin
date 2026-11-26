# Shopping list for Music Assistant 🛒🎧

A [Music Assistant](https://music-assistant.io) plugin that reads out and ticks off your
[Home Assistant](https://www.home-assistant.io) shopping list with the media controls of your
player, such as the controls of your headphones, while you are in a supermarket. The music keeps
playing.

| Control        | Normally       | In shopping mode                                           |
|----------------|----------------|------------------------------------------------------------|
| play/pause     | pause          | the current entry is read out                              |
| next           | next track     | the entry is ticked off (or deleted), the next one is read |
| previous       | previous track | the entry moves to the end of the list                     |

Each of the three can be switched off in the settings: then it does what it always does, also in
shopping mode. Outside of shopping mode all controls work as usual.

## How it works

- Shopping mode is on while a Home Assistant **person** is in one of the chosen **zones**, or
  while you started it **by hand** (see below).
- The entries come from a Home Assistant **to-do list** (`todo.get_items`) and are ticked off with
  `todo.update_item` (or deleted with `todo.remove_item`).
- Entries are spoken as **announcements** on your player.
- While shopping mode is on, the plugin switches on **Don't stop the music** for the player's
  queue, so there is always a next track, and switches it back afterwards (see below why).
- All of this goes through the connection of Music Assistant's own
  [Home Assistant plugin](https://music-assistant.io/ha-plugin/). The plugin talks to nothing else.

### How the controls are recognised

Music Assistant has no way yet for a plugin to take over the media controls of a player. The
plugin therefore watches what a control did to the player's queue and undoes it:

- **play/pause:** the music is halted, the entry is said, and the music goes on where it was.
  Some players cannot pause (Music Assistant then stops them), so a stop in the middle of a track
  counts as well.
- **next / previous:** the queue goes back to the track and position it was at, the entry is
  ticked off or skipped and the result is said. You may hear a short jump.

So next and previous can only be seen when they move the queue: on the last track of a queue
without a next one, next does nothing. That is why the plugin switches on Don't stop the music
while shopping. With repeat on, there is always a next track anyway.

A track that ends by itself does not count. Any pause, next or previous on that player while
shopping mode is on counts, whether it comes from the headphones, the car, a watch, the lock
screen or the app: the plugin cannot tell them apart.

A proper way for plugins to handle the media controls of a player would remove the gap and the
jump. That needs a change in Music Assistant itself, which is to be discussed with its
maintainers.

## Players

| Player | Status |
|---|---|
| [Music Assistant app](https://github.com/music-assistant/mobile-app) on Android | ✅ works |
| Music Assistant app on iOS | ❓ not tested |
| MassDroid | ❌ not supported: after its own pause it keeps the announcement silent, so play/pause reads out nothing |
| Other players | ❓ not tested: the player needs to forward its media controls to Music Assistant and play announcements |

### Not tested yet

- **Radio:** a radio station has no next track and no length, so next and previous may not be
  recognised there.

## The page

The plugin has a page of its own, in the main menu of the Music Assistant app under
**Shopping list**, in the theme and language you chose in the app (English for languages the
page does not have yet). It shows the list and whether shopping mode is on, starts and ends
shopping mode, reads out the current entry, ticks entries off and moves the current one to the
end.

## Several people and several shops

- **One player per person:** add the plugin once per person, each with their own person and
  player (their phone). Give each a name in its settings to tell them apart.
- **A list per zone:** after choosing the zones and saving, each zone gets a setting
  *Shopping list in …*, such as a drugstore list for the drugstore. Zones left empty use the
  shopping list of the plugin, and so does shopping mode started by hand outside of the zones.

## Requirements

- Music Assistant with the **Home Assistant plugin** set up.
- In Home Assistant: a **to-do list** (the built-in Shopping list is `todo.shopping_list`), and
  to start shopping mode by location a **person** with location tracking (e.g. the Companion
  app) and one or more **zones** for your shops.
- A **text-to-speech engine**: the Home Assistant plugin offers the text-to-speech services of
  Home Assistant, such as Google Translate or Piper.
- A supported **player** (see above).

## Setup

1. In Music Assistant, open **Settings → Plugins → Add** and choose **Shopping list**.
2. Fill in. The Home Assistant entities are offered to choose from; while Home Assistant is not
   reachable, entity ids can be typed instead.
   - **Player:** the player whose controls you use, usually your phone.
   - **Person** and **Supermarket zones:** to start shopping mode by location.
   - **Switch for shopping mode:** optional, e.g. `input_boolean.shopping_mode`.
   - **Shopping list:** e.g. `todo.shopping_list`, and after saving, optionally one per zone.
   - **Delete entries instead of ticking them off:** off by default.
   - **Language of the announcements:** English or German.
   - **Text-to-speech engine** and **Chime before announcements**.
   - **Play/pause**, **Next** and **Previous:** which controls shopping mode takes over.

## Starting shopping mode by hand

Shopping mode can also be on outside of the zones, for example in a shop you have no zone for:

- **The page of the plugin:** *Start shopping mode* and *End shopping mode*. Without a switch
  (below), shopping mode started this way ends when the plugin restarts, also after saving its
  settings.
- **A switch in Home Assistant** (optional): create a toggle helper, such as
  `input_boolean.shopping_mode` (*Settings → Devices & services → Helpers → Create helper →
  Toggle*), and enter it as *Switch for shopping mode*. While it is on, shopping mode is on.
  Switch it from a dashboard, a phone widget, by voice or from an automation; the page switches
  it too, and it survives restarts.

Leaving a zone does not end shopping mode that was started by hand, but *End shopping mode*
ends it also in a zone, until you leave the zone.

Shopping mode does not start for an empty list, and a control used when nothing is left ends it.
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
| `shopping_list/__init__.py` | The plugin: settings, shopping mode, reacting to the controls, the page |
| `shopping_list/gestures.py` | Recognises the controls from queue changes (no server needed, unit tested) |
| `shopping_list/shopping.py` | The list in the order it is walked through, and shopping mode |
| `shopping_list/home_assistant.py` | Zone states and the to-do calls to Home Assistant |
| `shopping_list/phrases.py` | What is said, in English and German |
| `shopping_list/page.py` | The page of the plugin |

## Licence

Apache-2.0
