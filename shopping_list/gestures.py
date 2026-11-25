"""
Recognise headphone button presses from the changes of a player queue.

Music Assistant has no way for a plugin to take over the transport commands of a player, so the
plugin watches what the commands did to the queue instead:

- one press (play/pause) pauses the queue at the same item: read the current entry; a player
  that cannot pause is stopped instead, which counts the same when the item was not about to end;
- two presses (next) move the queue to its next item before the item ended: tick the entry off;
  a queue without a next item does not move at all, so then the press cannot be seen;
- three presses (previous) move the queue one item back, or restart the current item: skip the
  entry.

For next and previous the queue is put back where it was, so the music goes on.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from music_assistant_models.enums import PlaybackState

# seconds before the end of an item in which a move to the next item counts as the item ending
END_MARGIN = 10
# previous restarts the current item instead of going back once this many seconds played
RESTART_THRESHOLD = 5
# below this elapsed time a restarted item counts as just started
JUST_STARTED = 1.5


class Gesture(StrEnum):
    """What a button press asks for."""

    READ = "read"
    COMPLETE = "complete"
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class QueueSnapshot:
    """The parts of a queue's state that the detection compares, taken at one moment."""

    index: int | None
    queue_item_id: str | None
    state: PlaybackState
    elapsed: float
    duration: int | None
    taken_at: float
    # the item the queue plays after this one: with repeat on, the first after the last
    next_queue_item_id: str | None = None

    def elapsed_at(self, now: float) -> float:
        """
        Return the elapsed time of the item at a later moment.

        :param now: The moment, as a ``time.time()`` value.
        """
        if self.state == PlaybackState.PLAYING:
            return self.elapsed + max(0.0, now - self.taken_at)
        return self.elapsed


@dataclass(frozen=True, slots=True)
class Detection:
    """A recognised button press and where to put the queue back to, if anywhere."""

    gesture: Gesture
    restore_index: int | None = None
    restore_position: int = 0


def detect_gesture(before: QueueSnapshot, after: QueueSnapshot, now: float) -> Detection | None:
    """
    Return the button press that turned one queue state into the next, or None.

    :param before: The last state of the queue that was seen.
    :param after: The new state of the queue.
    :param now: The moment the new state was seen, as a ``time.time()`` value.
    """
    if before.index is None or after.index is None:
        return None
    position = int(before.elapsed_at(now))
    near_end = bool(before.duration) and position >= (before.duration or 0) - END_MARGIN
    if after.index == before.index:
        return _same_item(before, after, position, near_end=near_end)
    to_next = after.index == before.index + 1 or (
        before.next_queue_item_id is not None and after.queue_item_id == before.next_queue_item_id
    )
    if to_next and not near_end:
        # a move at the end of the item is the item ending by itself
        return Detection(Gesture.COMPLETE, before.index, position)
    if after.index == before.index - 1:
        return Detection(Gesture.SKIP, before.index, position)
    # a jump of more than one item was chosen in an app, not pressed on headphones
    return None


def _same_item(
    before: QueueSnapshot, after: QueueSnapshot, position: int, *, near_end: bool
) -> Detection | None:
    """
    Return the button press that changed the queue without moving to another item, or None.

    :param before: The last state of the queue that was seen.
    :param after: The new state of the queue.
    :param position: The elapsed time of the item when the change was seen.
    :param near_end: Whether the item was about to end.
    """
    if before.state != PlaybackState.PLAYING:
        return None
    if after.state == PlaybackState.PAUSED:
        return Detection(Gesture.READ)
    if after.state == PlaybackState.IDLE:
        # Music Assistant stops a player that cannot pause; at the end of the item the queue
        # just ended
        return None if near_end else Detection(Gesture.READ)
    # previous restarts the item once a few seconds played
    restarted = (
        after.queue_item_id == before.queue_item_id
        and after.elapsed < JUST_STARTED
        and position > RESTART_THRESHOLD
        and not near_end
    )
    return Detection(Gesture.SKIP, before.index, position) if restarted else None
