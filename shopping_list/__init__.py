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

from music_assistant_models.config_entries import (
    ConfigActionResult,
    ConfigEntry,
    ConfigValueOption,
)
from music_assistant_models.enums import (
    ConfigEntryType,
    EventType,
    PlaybackState,
    PlayerFeature,
)
from music_assistant_models.errors import SetupFailedError

from music_assistant.helpers.plugin_engines import (
    create_tts_engine_config_entries,
    resolve_tts_engine_setting,
)
from music_assistant.models.plugin import PluginProvider

from .gestures import Detection, Gesture, QueueSnapshot, detect_gesture
from .home_assistant import (
    EntityStates,
    entity_options,
    finish_item,
    get_open_items,
    is_entity_id,
)
from .phrases import DEFAULT_LANGUAGE, PHRASES, Phrases, get_phrases
from .shopping import ShoppingList, ShoppingMode, TodoItem

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
CONF_SWITCH = "switch_entity"
CONF_TTS = "tts_engine"
CONF_CHIME = "chime"
ACTION_START = "start_shopping"
ACTION_STOP = "stop_shopping"
DEFAULT_TODO = "todo.shopping_list"
# the queue changes the plugin causes itself, by putting the queue back or resuming it, are no
# button presses: changes within this many seconds after a press are not looked at
OWN_CHANGES_SECONDS = 4.0
# how long a press waits for the music to play again before the entry is read anyway
RESUME_TIMEOUT = 8.0
# how long the music plays again before the announcement starts
SETTLE_SECONDS = 2.0
# the Home Assistant domains each entity setting offers to choose from
ENTITY_DOMAINS: dict[str, set[str]] = {
    CONF_PERSON: {"person"},
    CONF_ZONES: {"zone"},
    CONF_SWITCH: {"input_boolean", "switch"},
    CONF_TODO: {"todo"},
}


def config_entries(
    players: list[ConfigValueOption],
    entities: dict[str, list[ConfigValueOption]] | None = None,
) -> tuple[ConfigEntry, ...]:
    """
    Return the settings of the plugin.

    Everything without a default is optional, so the plugin can be added before the phone is
    known to Music Assistant; until a player is chosen, the plugin waits. The person and the
    zones are only needed to start shopping mode by location, the switch only to start it from
    Home Assistant. Without the entities of Home Assistant to choose from, entity ids are typed.

    :param players: The players to choose from.
    :param entities: Per entity setting, the entities of Home Assistant to choose from.
    """
    options = entities or {}
    return (
        ConfigEntry(key=CONF_PLAYER, type=ConfigEntryType.STRING, options=players, required=False),
        ConfigEntry(
            key=CONF_PERSON,
            type=ConfigEntryType.STRING,
            options=options.get(CONF_PERSON, []),
            required=False,
        ),
        ConfigEntry(
            key=CONF_ZONES,
            type=ConfigEntryType.STRING,
            multi_value=True,
            default_value=[],
            options=options.get(CONF_ZONES, []),
            required=False,
        ),
        ConfigEntry(
            key=CONF_SWITCH,
            type=ConfigEntryType.STRING,
            options=options.get(CONF_SWITCH, []),
            required=False,
        ),
        ConfigEntry(
            key=ACTION_START, type=ConfigEntryType.ACTION, action=ACTION_START, required=False
        ),
        ConfigEntry(
            key=ACTION_STOP, type=ConfigEntryType.ACTION, action=ACTION_STOP, required=False
        ),
        ConfigEntry(
            key=CONF_TODO,
            type=ConfigEntryType.STRING,
            default_value=DEFAULT_TODO,
            options=options.get(CONF_TODO, []),
        ),
        ConfigEntry(
            key=CONF_REMOVE, type=ConfigEntryType.BOOLEAN, default_value=False, required=False
        ),
        ConfigEntry(
            key=CONF_LANGUAGE,
            type=ConfigEntryType.STRING,
            default_value=DEFAULT_LANGUAGE,
            options=[ConfigValueOption(language) for language in PHRASES],
        ),
        ConfigEntry(
            key=CONF_CHIME, type=ConfigEntryType.BOOLEAN, default_value=False, required=False
        ),
    )


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
        self._mode = ShoppingMode()
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
        states = await self._all_states()
        entities = {
            key: entity_options(states, domains, self._values(key))
            for key, domains in ENTITY_DOMAINS.items()
        }
        tts = await create_tts_engine_config_entries(self.mass, CONF_TTS, category="generic")
        return (*config_entries(players, entities), *tts)

    async def _all_states(self) -> list[dict[str, Any]]:
        """Return the states of all Home Assistant entities, or none when it is not reachable."""
        try:
            hass = self._hass()
            if not hass.connected:
                return []
            return list(await hass.get_states())
        except Exception as err:  # noqa: BLE001 - the settings then take typed entity ids
            self.logger.debug("Could not list the entities of Home Assistant: %s", err)
            return []

    def _setting(self, key: str, default: str = "") -> str:
        """Return a text setting, stripped of spaces."""
        return str(self.config.get_value(key) or default).strip()

    @property
    def _player_id(self) -> str:
        return self._setting(CONF_PLAYER)

    def _values(self, key: str, default: str = "") -> list[str]:
        """Return the values of a setting: a list, or a text with commas between the values."""
        raw = self.config.get_value(key)
        values = raw if isinstance(raw, list) else str(raw or default).split(",")
        return [str(value).strip() for value in values if str(value).strip()]

    def _entities(self, key: str, default: str = "") -> list[str]:
        """Return the entity ids of a setting, without the ones misspelled."""
        return [value for value in self._values(key, default) if is_entity_id(value)]

    def _misspelled(self) -> list[str]:
        """Return the settings with a value that is no entity id, to say so in the log."""
        return [
            f"{key}={value!r}"
            for key in ENTITY_DOMAINS
            for value in self._values(key)
            if not is_entity_id(value)
        ]

    @property
    def _person(self) -> str:
        return next(iter(self._entities(CONF_PERSON)), "")

    @property
    def _zones(self) -> list[str]:
        return self._entities(CONF_ZONES)

    @property
    def _switch(self) -> str:
        return next(iter(self._entities(CONF_SWITCH)), "")

    @property
    def _todo(self) -> str:
        return next(iter(self._entities(CONF_TODO, DEFAULT_TODO)), DEFAULT_TODO)

    @property
    def _phrases(self) -> Phrases:
        return get_phrases(self._setting(CONF_LANGUAGE, DEFAULT_LANGUAGE))

    # lifecycle

    async def loaded_in_mass(self) -> None:
        """Start watching the zones, the switch and the player's queue."""
        if misspelled := self._misspelled():
            self.logger.warning(
                "Ignoring settings that are no Home Assistant entity id, like person.alex: %s",
                ", ".join(misspelled),
            )
        if not self._player_id:
            self.logger.warning("Choose the player in the settings of the plugin")
            return
        zones = [self._person, *self._zones] if self._person and self._zones else []
        if entities := [*zones, *([self._switch] if self._switch else [])]:
            self._unsubscribers.append(
                await self._hass().subscribe_entities(self._on_entities, entities)
            )
        else:
            self.logger.info("No zones or switch set: start shopping mode in the settings")
        self._unsubscribers.append(
            self.mass.subscribe(
                self._on_queue_event, (EventType.QUEUE_UPDATED, EventType.QUEUE_TIME_UPDATED)
            )
        )
        self.logger.info("Listening to the buttons of %s", self._player_id)

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

    # shopping mode

    async def handle_config_action(
        self, action: str
    ) -> tuple[ConfigEntry, ...] | ConfigActionResult | None:
        """Start or end shopping mode with the buttons in the settings."""
        if action not in {ACTION_START, ACTION_STOP}:
            return await super().handle_config_action(action)
        start = action == ACTION_START
        if self._switch:
            # the switch is the one place that says whether shopping mode was started by hand;
            # its new state comes back through the subscription
            await self._hass().call_service(
                "homeassistant",
                "turn_on" if start else "turn_off",
                target={"entity_id": self._switch},
            )
        else:
            self._mode.manual = start
            self._mode_changed()
        key = "started" if start else "stopped"
        return ConfigActionResult(message=f"Shopping mode {key}.", translation_key=key)

    def _on_entities(self, message: dict[str, Any]) -> None:
        """Follow the person, the zones and the switch."""
        self._states.apply(message)
        self._mode.zone = self._states.zone_of(self._person, self._zones)
        if self._switch:
            self._mode.manual = self._states.states.get(self._switch) == "on"
        self._mode_changed()

    def _mode_changed(self) -> None:
        """Say when shopping mode went on or off."""
        if not self._mode.switched():
            return
        self.logger.info("Shopping mode %s", "on" if self._mode.on else "off")
        self.mass.create_task(self._announce_mode())

    async def _announce_mode(self) -> None:
        """Say that shopping mode started or ended, when the player plays."""
        phrases = self._phrases
        if self._mode.on:
            await self._refresh()
            if self._mode.zone:
                text = phrases.activated.format(self._mode.zone, len(self._list))
            else:
                text = phrases.activated_manual.format(len(self._list))
        else:
            text = phrases.deactivated
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
        if before is None or (before.index, before.state, before.queue_item_id) != (
            snapshot.index,
            snapshot.state,
            snapshot.queue_item_id,
        ):
            # what a press does to the queue differs between apps: this shows it in the log
            self.logger.debug(
                "Queue %s: %s, index %s, %.1f of %s s (%s)",
                queue_id,
                snapshot.state,
                snapshot.index,
                snapshot.elapsed,
                snapshot.duration,
                event.event,
            )
        if (
            event.event != EventType.QUEUE_UPDATED
            or before is None
            or not self._mode.on
            # what the plugin does itself while it handles a press is no press
            or self._lock.locked()
            or now < self._ignore_until
        ):
            return
        if detection := detect_gesture(before, snapshot, now):
            self.logger.debug("Recognised %s", detection)
            self._ignore_until = now + OWN_CHANGES_SECONDS
            self.mass.create_task(self._handle(queue_id, detection))

    async def _handle(self, queue_id: str, detection: Detection) -> None:
        """Do what a press asks for and say the result, with the music the way it was."""
        async with self._lock:
            self.logger.debug("Button press: %s", detection)
            if self._announces_natively():
                await self._handle_over_music(queue_id, detection)
            else:
                await self._handle_in_silence(queue_id, detection)
            # the queue changes that putting the music back causes arrive a little later
            self._ignore_until = time.time() + OWN_CHANGES_SECONDS

    def _announces_natively(self) -> bool:
        """Return whether the player speaks an announcement over the music by itself."""
        player = self.mass.players.get_player(self._player_id)
        return player is not None and PlayerFeature.PLAY_ANNOUNCEMENT in player.supported_features

    async def _handle_over_music(self, queue_id: str, detection: Detection) -> None:
        """Put the music back first, then speak over it, for a player that lowers the music."""
        try:
            await self._resume(queue_id, detection)
            # one that starts while the music stream is still being set up loses its words
            if await self._wait_until_playing(queue_id):
                await asyncio.sleep(SETTLE_SECONDS)
        except Exception as err:  # noqa: BLE001 - the entry is still read when this fails
            self.logger.warning("Could not put the music back: %s", err)
        await self._announce(await self._respond(detection.gesture))

    async def _handle_in_silence(self, queue_id: str, detection: Detection) -> None:
        """
        Halt the music, speak, then put the music back, for a player without own announcements.

        Music Assistant stops such a player for an announcement and starts it again afterwards.
        Every switch between music and announcement is a chance for the player to lose the
        words, so the music is halted once, before the announcement, and put back once, after.
        """
        try:
            if detection.gesture != Gesture.READ:
                # the press already halted the music for reading; this also cancels the move
                # to another track that a next or previous still has pending
                await self.mass.player_queues.pause(queue_id)
        except Exception as err:  # noqa: BLE001 - the entry is still said when this fails
            self.logger.warning("Could not halt the music: %s", err)
        await self._announce(await self._respond(detection.gesture))
        try:
            await self._resume(queue_id, detection)
        except Exception as err:  # noqa: BLE001 - nothing else to do than to log it
            self.logger.warning("Could not put the music back: %s", err)

    async def _resume(self, queue_id: str, detection: Detection) -> None:
        """Play the music again, at the track and position it was at before the press."""
        if detection.restore_index is not None:
            await self.mass.player_queues.play_index(
                queue_id, detection.restore_index, seek_position=detection.restore_position
            )
        elif detection.gesture == Gesture.READ:
            await self.mass.players.cmd_play(self._player_id)

    async def _wait_until_playing(self, queue_id: str) -> bool:
        """Wait until the queue plays again, at most a few seconds, and return whether it does."""
        deadline = time.time() + RESUME_TIMEOUT
        while time.time() < deadline:
            queue = self.mass.player_queues.get(queue_id)
            if queue is not None and queue.state == PlaybackState.PLAYING:
                return True
            await asyncio.sleep(0.25)
        self.logger.debug("The music did not play again within %s s", RESUME_TIMEOUT)
        return False

    async def _respond(self, gesture: Gesture) -> str:
        """Do what a press asks for with the list and return what to say."""
        phrases = self._phrases
        if gesture == Gesture.READ:
            await self._refresh()
            # a lone word is too short for some players to be heard at all
            current = self._list.current
            return phrases.read.format(current.summary) if current else phrases.empty

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
            self.logger.warning(
                "Could not fetch %s, is it the entity id of a to-do list in Home Assistant? %s",
                self._todo,
                err,
            )

    async def _announce(self, text: str) -> None:
        """Speak a text on the player, over the music."""
        engine = await resolve_tts_engine_setting(self.mass, self.config.get_value(CONF_TTS))
        if engine is None:
            self.logger.warning(
                "Could not announce %r: choose a text-to-speech engine in the settings of the "
                "plugin; the Home Assistant plugin offers each tts entity of Home Assistant",
                text,
            )
            return
        try:
            await self.mass.players.play_announcement(
                self._player_id,
                message=text,
                pre_announce=bool(self.config.get_value(CONF_CHIME)),
                tts_engine=engine.uid,
                language=self._phrases.tts_language,
            )
        except Exception as err:  # noqa: BLE001 - nothing else to do than to log it
            self.logger.warning("Could not announce %r: %s", text, err)
