"""What the plugin says, per language of the announcements."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Phrases:
    """The sentences of one language; ``{}`` placeholders take entry or zone names."""

    tts_language: str
    activated: str
    deactivated: str
    empty: str
    completed: str
    completed_last: str
    skipped: str
    only_one: str
    failed: str


PHRASES: dict[str, Phrases] = {
    "de": Phrases(
        tts_language="de-DE",
        activated="Einkaufsmodus bei {}. {} Artikel auf der Liste.",
        deactivated="Einkaufsmodus beendet.",
        empty="Die Einkaufsliste ist leer.",
        completed="{} erledigt. Nächster: {}.",
        completed_last="{} erledigt. Alles eingekauft!",
        skipped="Später. Nächster: {}.",
        only_one="Nur noch {}.",
        failed="{} konnte nicht abgehakt werden.",
    ),
    "en": Phrases(
        tts_language="en-US",
        activated="Shopping mode at {}. {} items on the list.",
        deactivated="Shopping mode ended.",
        empty="The shopping list is empty.",
        completed="{} done. Next: {}.",
        completed_last="{} done. That was everything!",
        skipped="Later. Next: {}.",
        only_one="Only {} left.",
        failed="Could not tick off {}.",
    ),
}
DEFAULT_LANGUAGE = "de"


def get_phrases(language: str) -> Phrases:
    """
    Return the sentences of a language, German when the language is unknown.

    :param language: The language code from the settings, such as ``de``.
    """
    return PHRASES.get(language, PHRASES[DEFAULT_LANGUAGE])
