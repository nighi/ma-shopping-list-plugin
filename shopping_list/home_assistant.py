"""
Talk to Home Assistant over the connection of Music Assistant's own Home Assistant plugin.

Only two things are asked of Home Assistant: the state of a person and some zones, and the open
entries of a to-do list, which the plugin also ticks off or deletes.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from music_assistant_models.config_entries import ConfigValueOption

from .shopping import TodoItem

if TYPE_CHECKING:
    from hass_client import HomeAssistantClient


# a Home Assistant entity id: the domain, a dot and the object id, such as person.alex
ENTITY_ID = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+")


def is_entity_id(value: str) -> bool:
    """
    Return whether a text is shaped like a Home Assistant entity id.

    :param value: The text, such as ``person.alex``.
    """
    return ENTITY_ID.fullmatch(value) is not None


def entity_options(
    states: list[dict[str, Any]], domains: set[str], selected: list[str]
) -> list[ConfigValueOption]:
    """
    Return the entities of some domains as options to choose from, sorted by name.

    Chosen entities that Home Assistant does not list (any more) stay options, so opening the
    settings never drops them.

    :param states: The states of all entities, as ``get_states`` returns them.
    :param domains: The domains to offer, such as ``{"zone"}``.
    :param selected: The entity ids chosen so far.
    """
    titles: dict[str, str] = {}
    for state in states:
        entity_id = str(state.get("entity_id", ""))
        if entity_id.split(".", 1)[0] in domains and is_entity_id(entity_id):
            name = (state.get("attributes") or {}).get("friendly_name")
            titles[entity_id] = f"{name} ({entity_id})" if name else entity_id
    for entity_id in selected:
        titles.setdefault(entity_id, entity_id)
    return [
        ConfigValueOption(entity_id, title)
        for entity_id, title in sorted(titles.items(), key=lambda item: item[1].casefold())
    ]


class EntityStates:
    """
    The state and attributes of the watched entities.

    Kept up to date from the compressed messages of Home Assistant's ``subscribe_entities``:
    ``a`` adds entities with their full state, ``c`` changes them (``+`` sets values, ``-``
    removes attributes) and ``r`` removes entities.
    """

    def __init__(self) -> None:
        """Start without any known entity."""
        self.states: dict[str, str] = {}
        self.attributes: dict[str, dict[str, Any]] = {}

    def apply(self, message: dict[str, Any]) -> None:
        """
        Apply one ``subscribe_entities`` message.

        :param message: The event of the message.
        """
        for entity_id, full in message.get("a", {}).items():
            self.states[entity_id] = str(full.get("s", ""))
            self.attributes[entity_id] = dict(full.get("a", {}))
        for entity_id, diff in message.get("c", {}).items():
            if added := diff.get("+"):
                if "s" in added:
                    self.states[entity_id] = str(added["s"])
                self.attributes.setdefault(entity_id, {}).update(added.get("a", {}))
            if removed := diff.get("-"):
                for key in removed.get("a", []):
                    self.attributes.get(entity_id, {}).pop(key, None)
        for entity_id in message.get("r", []):
            self.states.pop(entity_id, None)
            self.attributes.pop(entity_id, None)

    def name_of(self, entity_id: str) -> str:
        """
        Return the name of an entity, or its entity id when it has none.

        :param entity_id: The entity id, such as ``zone.supermarket``.
        """
        return str(self.attributes.get(entity_id, {}).get("friendly_name") or entity_id)

    def zone_of(self, person: str, zones: list[str]) -> str | None:
        """
        Return the entity id of the first of the zones the person is in, or None.

        A zone lists the persons in it in its ``persons`` attribute; the state of a person is the
        name of the zone it is in, which is the fallback for zones that list nobody.

        :param person: The entity id of the person, such as ``person.alex``.
        :param zones: The entity ids of the zones, such as ``zone.supermarket``.
        """
        person_state = self.states.get(person)
        for zone in zones:
            attributes = self.attributes.get(zone, {})
            if person in (attributes.get("persons") or []) or person_state == self.name_of(zone):
                return zone
        return None


async def get_open_items(hass: HomeAssistantClient, todo_entity: str) -> list[TodoItem]:
    """
    Return the open entries of a to-do list.

    :param hass: The connected Home Assistant client.
    :param todo_entity: The entity id of the list, such as ``todo.shopping_list``.
    """
    command: dict[str, Any] = {
        "domain": "todo",
        "service": "get_items",
        "service_data": {"status": ["needs_action"]},
        "target": {"entity_id": todo_entity},
        "return_response": True,
    }
    result = await hass.send_command("call_service", **command)
    response = (result or {}).get("response") or {}
    items = (response.get(todo_entity) or {}).get("items") or []
    return [TodoItem.from_dict(item) for item in items if item.get("summary")]


async def finish_item(
    hass: HomeAssistantClient, todo_entity: str, item: TodoItem, *, remove: bool
) -> None:
    """
    Tick an entry off, or delete it.

    :param hass: The connected Home Assistant client.
    :param todo_entity: The entity id of the list.
    :param item: The entry.
    :param remove: Delete the entry instead of ticking it off.
    """
    if remove:
        await hass.call_service(
            "todo", "remove_item", {"item": item.key}, target={"entity_id": todo_entity}
        )
    else:
        await hass.call_service(
            "todo",
            "update_item",
            {"item": item.key, "status": "completed"},
            target={"entity_id": todo_entity},
        )
