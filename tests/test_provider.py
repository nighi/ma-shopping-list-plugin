"""Tests of the provider, loaded by a real server."""

from music_assistant_models.enums import FlowStepType, ProviderTier

from music_assistant.mass import MusicAssistant
from shopping_list import (
    CONF_COMPLETE,
    CONF_LANGUAGE,
    CONF_READ,
    CONF_SKIP,
    CONF_TODO,
    config_entries,
    zone_todo_key,
)
from shopping_list.page import page_language, render_page
from tests import DOMAIN


async def test_provider_loads(mass: MusicAssistant) -> None:
    """The server loads the provider from this repository as a community provider."""
    assert mass.get_provider_manifest(DOMAIN).tier == ProviderTier.COMMUNITY


async def test_needs_home_assistant(mass: MusicAssistant) -> None:
    """Without the Home Assistant plugin the server does not set the provider up."""
    step = await mass.config.setup_provider(DOMAIN)
    assert step.type == FlowStepType.ABORT
    assert step.reason == "missing_dependency"


def test_can_be_added_before_the_phone_is_known() -> None:
    """Only the settings with a default are required, so the plugin can be added at once."""
    required = {entry.key for entry in config_entries([]) if entry.required}
    assert required <= {CONF_TODO, CONF_LANGUAGE}


def test_each_zone_gets_a_list_setting() -> None:
    """Every chosen zone gets an optional setting for its own list, labelled with its name."""
    entries = config_entries([], zones=[("zone.rewe", "Rewe"), ("zone.dm", "dm")])
    by_key = {entry.key: entry for entry in entries}
    assert by_key[zone_todo_key("zone.rewe")].translation_params == ["Rewe"]
    assert by_key[zone_todo_key("zone.dm")].translation_key == "zone_todo"
    assert not by_key[zone_todo_key("zone.dm")].required
    assert zone_todo_key("zone.rewe") == "todo_for_zone_rewe"


def test_page_in_each_language_and_theme() -> None:
    """The page comes in German or English, in the user's theme or following the device."""
    assert "Einkaufsmodus starten" in render_page("de")
    assert 'data-theme="dark"' in render_page("de", theme="dark")
    assert 'data-theme="auto"' in render_page("de", theme="purple")
    english = render_page("xx")
    assert '<html lang="en" data-theme="auto">' in english
    assert "Start shopping mode" in english
    assert "__" not in english.replace("__TEXTS__", "")


def test_page_language() -> None:
    """The page speaks the user's language if it can, else English."""
    assert page_language("de_DE") == "de"
    assert page_language("fr") == "en"
    assert page_language("auto") == "en"
    assert page_language(None) == "en"


def test_each_control_can_be_left_alone() -> None:
    """Each of the three controls has a setting, on by default, to take it over or not."""
    by_key = {entry.key: entry for entry in config_entries([])}
    for key in (CONF_READ, CONF_COMPLETE, CONF_SKIP):
        assert by_key[key].default_value is True
