"""Switch entities for Mort Bay RF sockets."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
)

from . import MortBayConfigEntry
from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
    SUBENTRY_TYPE_SOCKET,
)
from .rf_dongle import RFDongle, RFDongleError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MortBayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Smart Wireless Socket entities."""

    _LOGGER.warning(
        "Loading Mort Bay switch platform with %s subentries",
        len(entry.subentries),
    )

    for subentry in entry.subentries.values():
        _LOGGER.warning(
            "Found subentry id=%s type=%s data=%s",
            subentry.subentry_id,
            subentry.subentry_type,
            dict(subentry.data),
        )

        if subentry.subentry_type != SUBENTRY_TYPE_SOCKET:
            _LOGGER.warning(
                "Skipping subentry because type %r != %r",
                subentry.subentry_type,
                SUBENTRY_TYPE_SOCKET,
            )
            continue

        entity = MortBayRFSwitch(
            dongle=entry.runtime_data.dongle,
            entry_id=entry.entry_id,
            controller_device_id=(
                entry.runtime_data.controller_device_id
            ),
            name=str(
                subentry.data.get(
                    CONF_NAME,
                    "Smart Wireless Socket",
                )
            ),
            device_id_hex=str(
                subentry.data[CONF_DEVICE_ID]
            ),
        )

        async_add_entities(
            [entity],
            config_subentry_id=subentry.subentry_id,
        )

        _LOGGER.warning(
            "Scheduled switch entity for subentry %s",
            subentry.subentry_id,
        )


class MortBayRFSwitch(SwitchEntity):
    """A Mort Bay Smart Wireless Socket."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:power-socket-au"

    def __init__(
        self,
        *,
        dongle: RFDongle,
        entry_id: str,
        controller_device_id: str,
        name: str,
        device_id_hex: str,
    ) -> None:
        """Initialize the RF socket."""
        self._dongle = dongle
        self._device_id_hex = device_id_hex.upper()
        self._device_id = bytes.fromhex(self._device_id_hex)

        self._attr_unique_id = (
            f"{entry_id}_socket_{self._device_id_hex.lower()}"
        )

        # Entity name becomes the device name only.
        self._attr_name = None

        self._attr_is_on: bool | None = None
        self._attr_available = True

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"socket:{entry_id}:{self._device_id_hex}",
                )
            },
            name=name,
            manufacturer="Mort Bay",
            model="Smart Wireless Socket",
            via_device_id=controller_device_id,
        )

    async def async_turn_on(
        self,
        **kwargs: Any,
    ) -> None:
        """Turn the socket on."""
        try:
            await self._dongle.async_turn_on(
                self._device_id
            )
        except RFDongleError:
            self._attr_available = False
            self.async_write_ha_state()
            raise

        self._attr_available = True
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(
        self,
        **kwargs: Any,
    ) -> None:
        """Turn the socket off."""
        try:
            await self._dongle.async_turn_off(
                self._device_id
            )
        except RFDongleError:
            self._attr_available = False
            self.async_write_ha_state()
            raise

        self._attr_available = True
        self._attr_is_on = False
        self.async_write_ha_state()
