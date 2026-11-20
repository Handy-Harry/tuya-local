"""Tests for the light entity."""

from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.components.climate import ClimateEntityFeature
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tuya_local.climate import TuyaLocalClimate, async_setup_entry
from custom_components.tuya_local.const import (
    CONF_DEVICE_ID,
    CONF_PROTOCOL_VERSION,
    CONF_TYPE,
    DOMAIN,
)
from custom_components.tuya_local.helpers.device_config import get_config


@pytest.mark.parametrize(
    ("readonly", "invalid", "enabled"),
    [(False, False, True), (True, False, False), (False, True, False)],
)
def test_target_temperature_feature_respects_writability(readonly, invalid, enabled):
    """Only remove target control, leaving unrelated features unchanged."""
    entity = Mock()
    entity._attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    dp = entity._temperature_dps
    dp.readonly = readonly
    dp.invalid_for.return_value = invalid
    original = entity._attr_supported_features

    features = TuyaLocalClimate.supported_features.fget(entity)

    assert bool(features & ClimateEntityFeature.TARGET_TEMPERATURE) is enabled
    assert features & ClimateEntityFeature.TURN_ON
    assert features & ClimateEntityFeature.TURN_OFF
    assert entity._attr_supported_features == original


def test_target_range_features_unchanged_without_single_target():
    """Do not change climates that use a target range instead."""
    entity = Mock()
    entity._temperature_dps = None
    entity._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    assert (
        TuyaLocalClimate.supported_features.fget(entity)
        == ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )


@pytest.mark.asyncio
async def test_aeno_smart_mode_target_control():
    """Use the real profile to verify mode changes and rejected manual writes."""
    state = {"1": True, "2": 25, "3": 20, "4": "smart"}
    device = Mock()
    device.get_property.side_effect = state.get
    device.async_set_properties = AsyncMock()
    config = next(
        entity
        for entity in get_config("aeno_ach0002s_heater").all_entities()
        if entity.entity == "climate"
    )
    entity = TuyaLocalClimate(device, config)

    assert entity.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    await entity.async_set_target_temperature(26)
    device.async_set_properties.assert_awaited_once()
    device.async_set_properties.reset_mock()

    for mode in ("manual", None):
        state["4"] = mode
        assert not entity.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
        assert entity.supported_features & ClimateEntityFeature.TURN_ON
        assert entity.supported_features & ClimateEntityFeature.TURN_OFF
        assert entity.current_temperature == 20
        with pytest.raises(AttributeError, match="cannot be set"):
            await entity.async_set_target_temperature(26)
        device.async_set_properties.assert_not_awaited()

    state["4"] = "smart"
    assert entity.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE


@pytest.mark.asyncio
async def test_init_entry(hass):
    """Test the initialisation."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: "heater",
            CONF_DEVICE_ID: "dummy",
            CONF_PROTOCOL_VERSION: "auto",
        },
    )
    # although async, the async_add_entities function passed to
    # async_setup_entry is called truly asynchronously. If we use
    # AsyncMock, it expects us to await the result.
    m_add_entities = Mock()
    m_device = AsyncMock()
    m_device.get_property = Mock(return_value=None)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["dummy"] = {}
    hass.data[DOMAIN]["dummy"]["device"] = m_device

    await async_setup_entry(hass, entry, m_add_entities)
    assert type(hass.data[DOMAIN]["dummy"]["climate"]) is TuyaLocalClimate
    m_add_entities.assert_called_once()


# After removal of deprecated entities, there are no secondary climate devices to test against.
# async def test_init_entry_as_secondary(hass):
#     """Test initialisation when climate is a secondary entity"""
#     entry = MockConfigEntry(
#         domain=DOMAIN,
#         data={
#             CONF_TYPE: "goldair_dehumidifier",
#             CONF_DEVICE_ID: "dummy",
#         },
#     )
#     # although async, the async_add_entities function passed to
#     # async_setup_entry is called truly asynchronously. If we use
#     # AsyncMock, it expects us to await the result.
#     m_add_entities = Mock()
#     m_device = AsyncMock()

#     hass.data[DOMAIN] = {}
#     hass.data[DOMAIN]["dummy"] = {}
#     hass.data[DOMAIN]["dummy"]["device"] = m_device

#     await async_setup_entry(hass, entry, m_add_entities)
#     assert (
#         type(hass.data[DOMAIN]["dummy"]["climate_dehumidifier_as_climate"])
#         is TuyaLocalClimate
#     )
#     m_add_entities.assert_called_once()


@pytest.mark.asyncio
async def test_init_entry_fails_if_device_has_no_climate(hass):
    """Test initialisation when device has no matching entity"""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: "smartplugv1",
            CONF_DEVICE_ID: "dummy",
            CONF_PROTOCOL_VERSION: "auto",
        },
    )
    # although async, the async_add_entities function passed to
    # async_setup_entry is called truly asynchronously. If we use
    # AsyncMock, it expects us to await the result.
    m_add_entities = Mock()
    m_device = AsyncMock()

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["dummy"] = {}
    hass.data[DOMAIN]["dummy"]["device"] = m_device
    try:
        await async_setup_entry(hass, entry, m_add_entities)
        assert False
    except ValueError:
        pass
    m_add_entities.assert_not_called()


@pytest.mark.asyncio
async def test_init_entry_fails_if_config_is_missing(hass):
    """Test initialisation when device has no matching entity"""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_TYPE: "non_existing",
            CONF_DEVICE_ID: "dummy",
            CONF_PROTOCOL_VERSION: "auto",
        },
    )
    # although async, the async_add_entities function passed to
    # async_setup_entry is called truly asynchronously. If we use
    # AsyncMock, it expects us to await the result.
    m_add_entities = Mock()
    m_device = AsyncMock()

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["dummy"] = {}
    hass.data[DOMAIN]["dummy"]["device"] = m_device
    try:
        await async_setup_entry(hass, entry, m_add_entities)
        assert False
    except ValueError:
        pass
    m_add_entities.assert_not_called()
