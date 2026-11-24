"""Tests of the shopping list and the Home Assistant helpers."""

from typing import Any

from shopping_list.home_assistant import EntityStates, finish_item, get_open_items
from shopping_list.phrases import get_phrases
from shopping_list.shopping import ShoppingList, TodoItem

MILK, BREAD, EGGS = TodoItem("Milk", "1"), TodoItem("Bread", "2"), TodoItem("Eggs", "3")


def test_list_keeps_walked_order() -> None:
    """Skipped entries stay at the end after a refresh, new ones are added after them."""
    shopping = ShoppingList()
    shopping.update([MILK, BREAD])
    assert shopping.skip() == BREAD
    shopping.update([MILK, BREAD, EGGS])
    assert shopping.items == [BREAD, MILK, EGGS]
    shopping.remove(BREAD)
    assert shopping.current == MILK
    shopping.update([EGGS])
    assert shopping.items == [EGGS]
    assert len(shopping) == 1


def test_skip_with_one_entry_keeps_it() -> None:
    """Skipping the only entry keeps it current."""
    shopping = ShoppingList()
    shopping.update([MILK])
    assert shopping.skip() == MILK


def test_item_key_falls_back_to_name() -> None:
    """An entry without uid is addressed by its name."""
    assert TodoItem.from_dict({"summary": "Salt"}).key == "Salt"
    assert TodoItem.from_dict({"summary": "Salt", "uid": "x"}).key == "x"


def test_zone_from_persons_and_from_person_state() -> None:
    """A person is in a zone when the zone lists it, or when its state is the zone's name."""
    states = EntityStates()
    states.apply(
        {
            "a": {
                "person.alex": {"s": "not_home", "a": {}},
                "zone.shop": {"s": "0", "a": {"friendly_name": "Shop", "persons": []}},
                "zone.market": {"s": "0", "a": {"friendly_name": "Market"}},
            }
        }
    )
    zones = ["zone.shop", "zone.market"]
    assert states.zone_of("person.alex", zones) is None
    states.apply({"c": {"zone.shop": {"+": {"s": "1", "a": {"persons": ["person.alex"]}}}}})
    assert states.zone_of("person.alex", zones) == "Shop"
    states.apply({"c": {"zone.shop": {"-": {"a": ["persons"]}}}})
    states.apply({"c": {"person.alex": {"+": {"s": "Market"}}}})
    assert states.zone_of("person.alex", zones) == "Market"
    states.apply({"r": ["zone.market"]})
    assert states.zone_of("person.alex", zones) is None


class FakeHass:
    """Records the commands sent to Home Assistant and answers get_items."""

    def __init__(self) -> None:
        """Start without commands."""
        self.commands: list[tuple[str, dict[str, Any]]] = []

    async def send_command(self, command: str, **kwargs: Any) -> dict[str, Any]:
        """Answer get_items with two entries, one of them without a name."""
        self.commands.append((command, kwargs))
        items = [{"summary": "Milk", "uid": "1"}, {"summary": "", "uid": "2"}]
        return {"response": {"todo.shopping_list": {"items": items}}}

    async def call_service(
        self, domain: str, service: str, data: dict[str, Any], target: dict[str, Any]
    ) -> None:
        """Record a service call."""
        self.commands.append((f"{domain}.{service}", {**data, **target}))


async def test_get_open_items() -> None:
    """The open entries are fetched with get_items, skipping entries without a name."""
    hass = FakeHass()
    assert await get_open_items(hass, "todo.shopping_list") == [MILK]
    command, kwargs = hass.commands[0]
    assert command == "call_service"
    assert kwargs["return_response"] is True
    assert kwargs["service_data"] == {"status": ["needs_action"]}


async def test_finish_item_ticks_off_or_deletes() -> None:
    """An entry is ticked off by default and deleted when asked."""
    hass = FakeHass()
    await finish_item(hass, "todo.list", MILK, remove=False)
    await finish_item(hass, "todo.list", MILK, remove=True)
    assert hass.commands == [
        ("todo.update_item", {"item": "1", "status": "completed", "entity_id": "todo.list"}),
        ("todo.remove_item", {"item": "1", "entity_id": "todo.list"}),
    ]


def test_unknown_language_falls_back_to_german() -> None:
    """An unknown language speaks German."""
    assert get_phrases("xx").tts_language == "de-DE"
    assert get_phrases("en").tts_language == "en-US"
