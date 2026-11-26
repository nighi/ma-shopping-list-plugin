"""The shopping list as the plugin walks through it: the first open entry is the current one."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TodoItem:
    """One open entry of a Home Assistant to-do list."""

    summary: str
    uid: str | None = None

    @property
    def key(self) -> str:
        """Return what the to-do actions of Home Assistant accept as ``item``: the uid or name."""
        return self.uid or self.summary

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TodoItem:
        """
        Create an entry from an item of the ``todo.get_items`` response.

        :param data: The item as Home Assistant returns it.
        """
        return cls(summary=str(data.get("summary", "")), uid=data.get("uid"))


class ShoppingList:
    """
    The open entries in the order the user walks through them.

    Skipped entries go to the end. A refresh keeps that order for the entries that are still open
    and adds new ones at the end.
    """

    def __init__(self) -> None:
        """Start with an empty list."""
        self._items: list[TodoItem] = []

    @property
    def items(self) -> list[TodoItem]:
        """Return the open entries, the current one first."""
        return list(self._items)

    @property
    def current(self) -> TodoItem | None:
        """Return the current entry, or None when the list is empty."""
        return self._items[0] if self._items else None

    def __len__(self) -> int:
        """Return the number of open entries."""
        return len(self._items)

    def update(self, fresh: list[TodoItem]) -> None:
        """
        Take over the open entries from Home Assistant, keeping the order walked so far.

        :param fresh: The open entries as Home Assistant has them now.
        """
        by_key = {item.key: item for item in reversed(fresh)}
        kept = [by_key[item.key] for item in self._items if item.key in by_key]
        known = {item.key for item in kept}
        added: list[TodoItem] = []
        for item in fresh:
            if item.key not in known:
                known.add(item.key)
                added.append(item)
        self._items = kept + added

    def remove(self, item: TodoItem) -> None:
        """
        Drop an entry that was ticked off or deleted.

        :param item: The entry to drop.
        """
        self._items = [entry for entry in self._items if entry.key != item.key]

    def skip(self) -> TodoItem | None:
        """Move the current entry to the end and return the new current entry."""
        if len(self._items) > 1:
            self._items.append(self._items.pop(0))
        return self.current


class ShoppingMode:
    """
    Whether shopping mode is on: while the person is in a zone, or while it was started by hand.

    Leaving the zone does not end a mode that was started by hand. A finished list ends shopping
    mode: one started by hand goes off, and the zone the person is in does not start it again
    until the person has left it.
    """

    def __init__(self) -> None:
        """Start with shopping mode off."""
        self._zone: str | None = None
        self._manual = False
        self._done = False
        self._was_on = False

    @property
    def zone(self) -> str | None:
        """Return the name of the zone the person is in, or None."""
        return self._zone

    @zone.setter
    def zone(self, zone: str | None) -> None:
        if zone is None:
            # leaving the zone of a finished list lets the next zone start shopping mode again
            self._done = False
        self._zone = zone

    @property
    def manual(self) -> bool:
        """Return whether shopping mode was started by hand."""
        return self._manual

    @manual.setter
    def manual(self, manual: bool) -> None:
        if manual and not self._manual:
            self._done = False
        self._manual = manual

    @property
    def on(self) -> bool:
        """Return whether shopping mode is on."""
        return self._manual or (self._zone is not None and not self._done)

    def finish(self) -> None:
        """End shopping mode because the list is done."""
        self._manual = False
        self._done = True

    def switched(self) -> bool:
        """Return whether shopping mode went on or off since the last call."""
        switched = self.on != self._was_on
        self._was_on = self.on
        return switched
