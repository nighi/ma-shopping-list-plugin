"""Tests of recognising button presses from queue changes."""

from music_assistant_models.enums import PlaybackState

from shopping_list.gestures import Detection, Gesture, QueueSnapshot, detect_gesture

NOW = 1000.0
PLAYING = PlaybackState.PLAYING


def snap(
    index: int,
    elapsed: float,
    state: PlaybackState = PLAYING,
    duration: int | None = 200,
    taken_at: float = NOW,
) -> QueueSnapshot:
    """Return a queue snapshot whose item id follows the index."""
    return QueueSnapshot(index, f"item{index}", state, elapsed, duration, taken_at)


def test_pause_reads() -> None:
    """Play/pause pauses at the same item: read."""
    after = snap(3, 60, PlaybackState.PAUSED)
    assert detect_gesture(snap(3, 60), after, NOW) == Detection(Gesture.READ)


def test_stop_of_a_player_that_cannot_pause_reads() -> None:
    """A player that cannot pause is stopped instead: that reads too, but not at the end."""
    after = snap(3, 60, PlaybackState.IDLE)
    assert detect_gesture(snap(3, 60), after, NOW) == Detection(Gesture.READ)
    assert detect_gesture(snap(3, 195), snap(3, 195, PlaybackState.IDLE), NOW) is None


def test_next_completes_and_restores_position() -> None:
    """Next before the end of the item: tick off, and go back to where the music was."""
    before = snap(3, 60, taken_at=NOW - 2)
    assert detect_gesture(before, snap(4, 0), NOW) == Detection(Gesture.COMPLETE, 3, 62)


def test_item_ending_is_no_press() -> None:
    """The queue moving on at the end of an item is not a press."""
    assert detect_gesture(snap(3, 195), snap(4, 0), NOW) is None


def test_next_without_duration_completes() -> None:
    """An item without a duration never ends by itself, so a move is a press."""
    before = snap(3, 60, duration=None)
    assert detect_gesture(before, snap(4, 0), NOW) == Detection(Gesture.COMPLETE, 3, 60)


def test_previous_skips() -> None:
    """Previous to the item before: skip, and go back to where the music was."""
    assert detect_gesture(snap(3, 2), snap(2, 0), NOW) == Detection(Gesture.SKIP, 3, 2)


def test_previous_restarting_the_item_skips() -> None:
    """Previous after five seconds restarts the item: skip as well."""
    assert detect_gesture(snap(3, 60), snap(3, 0), NOW) == Detection(Gesture.SKIP, 3, 60)


def test_other_changes_are_no_press() -> None:
    """A jump, a resume, a seek or an unknown index is not a press."""
    assert detect_gesture(snap(3, 60), snap(7, 0), NOW) is None
    assert detect_gesture(snap(3, 60, PlaybackState.PAUSED), snap(3, 60), NOW) is None
    assert detect_gesture(snap(3, 60), snap(3, 120), NOW) is None
    assert detect_gesture(snap(3, 2), snap(3, 0), NOW) is None
    unknown = QueueSnapshot(None, None, PLAYING, 0, None, NOW)
    assert detect_gesture(unknown, snap(4, 0), NOW) is None
