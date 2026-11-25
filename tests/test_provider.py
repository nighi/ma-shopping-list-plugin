"""Tests of the provider, loaded by a real server."""

from music_assistant_models.enums import FlowStepType, ProviderTier

from music_assistant.mass import MusicAssistant
from shopping_list import CONF_LANGUAGE, CONF_TODO, config_entries
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
