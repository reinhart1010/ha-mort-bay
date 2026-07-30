"""Mort Bay RF power-plug integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DEFAULT_PRODUCT_ID,
    DEFAULT_VENDOR_ID,
    PLATFORMS,
)
from .rf_dongle import (
    DongleAddress,
    RFDongle,
    RFDongleError,
)


@dataclass(slots=True)
class MortBayRuntimeData:
    """Runtime objects belonging to one config entry."""

    dongle: RFDongle


type MortBayConfigEntry = ConfigEntry[MortBayRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MortBayConfigEntry,
) -> bool:
    """Set up Mort Bay RF from a config entry."""
    dongle = RFDongle(
        hass,
        DongleAddress(
            vendor_id=entry.data.get(
                "vendor_id",
                DEFAULT_VENDOR_ID,
            ),
            product_id=entry.data.get(
                "product_id",
                DEFAULT_PRODUCT_ID,
            ),
        ),
    )

    try:
        await dongle.async_connect()
    except RFDongleError as err:
        raise ConfigEntryNotReady(
            f"RF USB dongle is unavailable: {err}"
        ) from err

    entry.runtime_data = MortBayRuntimeData(dongle=dongle)

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: MortBayConfigEntry,
) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if unloaded:
        await entry.runtime_data.dongle.async_disconnect()

    return unloaded
