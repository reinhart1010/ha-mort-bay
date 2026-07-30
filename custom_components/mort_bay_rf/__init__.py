"""Mort Bay RF power-plug integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    DEFAULT_PRODUCT_ID,
    DEFAULT_VENDOR_ID,
    DOMAIN,
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
    controller_device_id: str


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

    device_registry = dr.async_get(hass)

    controller_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={
            (
                DOMAIN,
                f"controller:{entry.entry_id}",
            )
        },
        name="Mort Bay Smart USB Wireless Controller",
        manufacturer="Mort Bay",
        model="Smart USB Wireless Controller",
    )

    entry.runtime_data = MortBayRuntimeData(
        dongle=dongle,
        controller_device_id=controller_device.id,
    )

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
