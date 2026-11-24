"""
Shopping list plugin for Music Assistant.

While a person is in one of the chosen Home Assistant zones (a supermarket), the headphone
buttons of one player walk through a Home Assistant to-do list, and the music keeps playing:

- one press (play/pause) reads the current entry;
- two presses (next) tick the current entry off, or delete it, and read the next one;
- three presses (previous) move the current entry to the end of the list.

The entries are spoken as announcements on the player, over the music. The plugin uses the
connection of Music Assistant's own Home Assistant plugin, which has to be set up first.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, cast

from music_assistant_models.config_entries import ConfigEntry, ConfigValueOption
from music_assistant_models.enums import ConfigEntryType, EventType, PlaybackState
from music_assistant_models.errors import SetupFailedError

from music_assistant.models.plugin import PluginProvider

from .gestures import Detection, Gesture, QueueSnapshot, detect_gesture
from .home_assistant import EntityStates, finish_item, get_open_items
from .phrases import DEFAULT_LANGUAGE, PHRASES, Phrases, get_phrases
from .shopping import ShoppingList, TodoItem

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from hass_client import HomeAssistantClient
    from music_assistant_models.config_entries import ProviderConfig
    from music_assistant_models.event import MassEvent
    from music_assistant_models.provider import ProviderManifest

    from music_assistant.mass import MusicAssistant
    from music_assistant.models import ProviderInstanceType
    from music_assistant.providers.hass import HomeAssistantProvider

HASS_DOMAIN = "hass"
CONF_PLAYER = "player_id"
CONF_PERSON = "person_entity"
CONF_ZONES = "zone_entities"
CONF_TODO = "todo_entity"
CONF_REMOVE = "remove_items"
CONF_LANGUAGE = "language"
DEFAULT_TODO = "todo.shopping_list"
# the queue changes the plugin causes itself, by putting the queue back or resuming it, are no
# button presses: changes within this many seconds after a press are not looked at
OWN_CHANGES_SECONDS = 4.0
AFTER_ANNOUNCEMENT_SECONDS = 1.5


async def setup(
    mass: MusicAssistant, manifest: ProviderManifest, config: ProviderConfig
) -> ProviderInstanceType:
    """Initialize the plugin for one settings entry."""
    if mass.get_provider(HASS_DOMAIN) is None:
        msg = "Set up the Home Assistant plugin of Music Assistant first."
        raise SetupFailedError(msg)
    return ShoppingListProvider(mass, manifest, config, set())


class ShoppingListProvider(PluginProvider):
    """Reads and ticks off a Home Assistant shopping list with the headphone buttons."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the plugin; it starts working in ``loaded_in_mass``."""
        super().__init__(*args, **kwargs)
        self._list = ShoppingList()
        self._states = EntityStates()
        self._zone: str | None = None
        self._snapshot: QueueSnapshot | None = None
        self._ignore_until = 0.0
        self._lock = asyncio.Lock()
        self._unsubscribers: list[Callable[[], None]] = []

    # settings

    async def get_config_entries(self) -> tuple[ConfigEntry, ...]:
        """Return the settings of the plugin."""
        players = [
            ConfigValueOption(player.player_id, player.name)
            for player in self.mass.players.all_players(return_unavailable=True)
        ]
        return (
            ConfigEntry(key=CONF_PLAYER, type=ConfigEntryType.STRING, options=players),
            ConfigEntry(key=CONF_PERSON, type=ConfigEntryType.STRING),
            ConfigEntry(key=CONF_ZONES, type=ConfigEntryType.STRING),
            ConfigEntry(key=CONF_TODO, type=ConfigEntryType.STRING, default_value=DEFAULT_TODO),
            ConfigEntry(
                key=CONF_REMOVE, type=ConfigEntryType.BOOLEAN, default_value=False, required=False
            ),
            ConfigEntry(
                key=CONF_LANGUAGE,
                type=ConfigEntryType.STRING,
                default_value=DEFAULT_LANGUAGE,
                options=[ConfigValueOption(language) for language in PHRASES],
            ),
        )

    def _setting(self, key: str, default: str = "") -> str:
        """Return a text setting, stripped of spaces."""
        return str(self.config.get_value(key) or default).strip()

    @property
    def _player_id(self) -> str:
        return self._setting(CONF_PLAYER)

    @property
    def _person(self) -> str:
        return self._setting(CONF_PERSON)

    @property
    def _zones(self) -> list[str]:
        return [zone.strip() for zone in self._setting(CONF_ZONES).split(",") if zone.strip()]

    @property
    def _todo(self) -> str:
        return self._setting(CONF_TODO, DEFAULT_TODO)

    @property
    def _phrases(self) -> Phrases:
        return get_phrases(self._setting(CONF_LANGUAGE, DEFAULT_LANGUAGE))

    # lifecycle

    async def loaded_in_mass(self) -> None:
        """Start watching the zones and the player's queue."""
        if not (self._player_id and self._person and self._zones):
            self.logger.warning(
                "Choose the player, the person and the zones in the settings of the plugin"
            )
            return
        hass = self._hass()
        self._unsubscribers.append(
            await hass.subscribe_entities(self._on_entities, [self._person, *self._zones])
        )
        self._unsubscribers.append(
            self.mass.subscribe(
                self._on_queue_event, (EventType.QUEUE_UPDATED, EventType.QUEUE_TIME_UPDATED)
            )
        )

    async def unload(self, is_removed: bool = False) -> None:  # noqa: FBT001, FBT002
        """Stop watching."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

    def _hass(self) -> HomeAssistantClient:
        """Return the client of Music Assistant's Home Assistant plugin."""
        provider = self.mass.get_provider(HASS_DOMAIN)
        if provider is None:
            msg = "The Home Assistant plugin of Music Assistant is not loaded."
            raise SetupFailedError(msg)
        return cast("HomeAssistantProvider", provider).hass

    # zones

    def _on_entities(self, message: dict[str, Any]) -> None:
        """Follow the person and the zones, and start or end shopping mode."""
        self._states.apply(message)
        zone = self._states.zone_of(self._person, self._zones)
        if zone == self._zone:
            return
        self._zone = zone
        self.logger.info("Shopping mode %s", f"on at {zone}" if zone else "off")
        self.mass.create_task(self._on_zone_changed(zone))

    async def _on_zone_changed(self, zone: str | None) -> None:
        """Say that shopping mode started or ended, when the player plays."""
        if zone:
            await self._refresh()
            text = self._phrases.activated.format(zone, len(self._list))
        else:
            text = self._phrases.deactivated
        if self._player_plays():
            await self._announce(text)

    def _player_plays(self) -> bool:
        player = self.mass.players.get_player(self._player_id)
        return player is not None and player.playback_state == PlaybackState.PLAYING

    # button presses

    def _queue_id(self) -> str:
        """Return the queue the player plays from: its own or the one it is synced to."""
        queue = self.mass.player_queues.get_active_queue(self._player_id)
        return queue.queue_id if queue else self._player_id

    def _on_queue_event(self, event: MassEvent) -> None:
        """
        Compare each new state of the player's queue with the last one.

        A plain (not async) callback, so the state is read as close as possible to the change.
        """
        queue_id = self._queue_id()
        if event.object_id != queue_id or (queue := self.mass.player_queues.get(queue_id)) is None:
            return
        now = time.time()
        item = queue.current_item
        snapshot = QueueSnapshot(
            index=queue.current_index,
            queue_item_id=item.queue_item_id if item else None,
            state=queue.state,
            elapsed=queue.corrected_elapsed_time,
            duration=item.duration if item else None,
            taken_at=now,
        )
        before, self._snapshot = self._snapshot, snapshot
        if (
            event.event != EventType.QUEUE_UPDATED
            or before is None
            or self._zone is None
            or now < self._ignore_until
        ):
            return
        if detection := detect_gesture(before, snapshot, now):
            self._ignore_until = now + OWN_CHANGES_SECONDS
            self.mass.create_task(self._handle(queue_id, detection))

    async def _handle(self, queue_id: str, detection: Detection) -> None:
        """Put the music back the way it was, do what the press asks for and say the result."""
        async with self._lock:
            self.logger.debug("Button press: %s", detection)
            try:
                if detection.restore_index is not None:
                    await self.mass.player_queues.play_index(
                        queue_id, detection.restore_index, seek_position=detection.restore_position
                    )
                elif detection.gesture == Gesture.READ:
                    await self.mass.players.cmd_play(self._player_id)
            except Exception as err:  # noqa: BLE001 - the entry is still read when this fails
                self.logger.warning("Could not put the music back: %s", err)
            self._ignore_until = time.time() + OWN_CHANGES_SECONDS
            text = await self._respond(detection.gesture)
            await self._announce(text)
            # an announcement can change the queue's state for a moment as well
            self._ignore_until = max(self._ignore_until, time.time() + AFTER_ANNOUNCEMENT_SECONDS)

    async def _respond(self, gesture: Gesture) -> str:
        """Do what a press asks for with the list and return what to say."""
        phrases = self._phrases
        if gesture == Gesture.READ:
            await self._refresh()
            return self._list.current.summary if self._list.current else phrases.empty

        item = self._list.current
        if item is None:
            return phrases.empty

        if gesture == Gesture.SKIP:
            if len(self._list) == 1:
                return phrases.only_one.format(item.summary)
            following = self._list.skip()
            assert following is not None
            return phrases.skipped.format(following.summary)
        return await self._complete(item)

    async def _complete(self, item: TodoItem) -> str:
        """Tick an entry off, or delete it, and return what to say."""
        phrases = self._phrases
        try:
            await finish_item(
                self._hass(), self._todo, item, remove=bool(self.config.get_value(CONF_REMOVE))
            )
        except Exception as err:  # noqa: BLE001 - a failure is said, not raised
            self.logger.warning("Could not tick off %s: %s", item.summary, err)
            return phrases.failed.format(item.summary)
        self._list.remove(item)
        if following := self._list.current:
            return phrases.completed.format(item.summary, following.summary)
        return phrases.completed_last.format(item.summary)

    # Home Assistant and announcements

    async def _refresh(self) -> None:
        """Fetch the open entries of the list."""
        try:
            self._list.update(await get_open_items(self._hass(), self._todo))
        except Exception as err:  # noqa: BLE001 - the last known list is used instead
            self.logger.warning("Could not fetch %s: %s", self._todo, err)

    async def _announce(self, text: str) -> None:
        """Speak a text on the player, over the music."""
        try:
            await self.mass.players.play_announcement(
                self._player_id, message=text, language=self._phrases.tts_language
            )
        except Exception as err:  # noqa: BLE001 - nothing else to do than to log it
            self.logger.warning("Could not announce %r: %s", text, err)
