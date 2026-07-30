"""Switch entities for Mort Bay RF power plugs."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
)

from . import MortBayConfigEntry
from .const import CONF_DEVICE_ID, CONF_PLUGS, DOMAIN, SUBENTRY_TYPE_SOCKET
from .rf_dongle import RFDongle, RFDongleError


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MortBayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RF socket entities."""
    dongle = entry.runtime_data.dongle

    entities = []

    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_SOCKET:
            continue

        entities.append(
            MortBayRFSwitch(
                dongle=dongle,
                entry_id=entry.entry_id,
                subentry_id=subentry.subentry_id,
                name=subentry.data[CONF_NAME],
                device_id_hex=subentry.data[CONF_DEVICE_ID],
            )
        )

    async_add_entities(entities)


class MortBayRFSwitch(SwitchEntity):
    """A one-way RF controlled power plug."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:power-socket-au"

    def __init__(
        self,
        *,
        dongle: RFDongle,
        entry_id: str,
        subentry_id: str,
        name: str,
        device_id_hex: str,
    ) -> None:
        self._dongle = dongle
        self._device_id_hex = device_id_hex.upper()
        self._device_id = bytes.fromhex(self._device_id_hex)

        self._attr_name = name
        self._attr_unique_id = (
            f"{entry_id}_{self._device_id_hex.lower()}"
        )

        self._attr_icon = "mdi:power-socket-au"
        self._attr_is_on = None
        self._attr_available = True

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{entry_id}:{self._device_id_hex}",
                )
            },
            name=name,
            manufacturer="Mort Bay",
            model="Smart Wireless Socket",
        )

        self._attr_config_entry_id = entry_id
        self._attr_config_subentry_id = subentry_id

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes."""
        return {
            "rf_device_id": self._device_id_hex,
            "state_source": "last_command",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the socket on."""
        try:
            await self._dongle.async_turn_on(self._device_id)
        except RFDongleError:
            self._attr_available = False
            self.async_write_ha_state()
            raise

        self._attr_available = True
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the socket off."""
        try:
            await self._dongle.async_turn_off(self._device_id)
        except RFDongleError:
            self._attr_available = False
            self.async_write_ha_state()
            raise

        self._attr_available = True
        self._attr_is_on = False
        self.async_write_ha_state()
