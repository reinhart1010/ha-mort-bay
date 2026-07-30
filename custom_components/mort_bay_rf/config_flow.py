from __future__ import annotations

import re
import secrets
from typing import Any

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_NAME
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CONF_DEVICE_ID,
    DEFAULT_SOCKET_NAME,
    DEFAULT_PRODUCT_ID,
    DEFAULT_VENDOR_ID,
    DOMAIN,
    SUBENTRY_TYPE_SOCKET,
)

CONF_ID_MODE = "id_mode"

ID_MODE_RANDOM = "random"
ID_MODE_MANUAL = "manual"

ID_PATTERN = re.compile(r"^[0-9A-F]{4}$")


def normalise_device_id(value: str) -> str:
    """Normalize a two-byte RF identifier."""
    compact = (
        value.strip()
        .replace(":", "")
        .replace("-", "")
        .replace(" ", "")
        .upper()
    )

    if not ID_PATTERN.fullmatch(compact):
        raise ValueError(
            "Device ID must contain exactly four hexadecimal digits"
        )

    if compact in {"0000", "FFFF"}:
        raise ValueError("Reserved device ID")

    return compact


def generate_device_id(existing_ids: set[str]) -> str:
    """Generate an unused two-byte RF identifier."""
    while True:
        candidate = secrets.token_hex(2).upper()

        if (
            candidate not in existing_ids
            and candidate not in {"0000", "FFFF"}
        ):
            return candidate


class MortBayRFConfigFlow(
    ConfigFlow,
    domain=DOMAIN,
):
    """Configure the Mort Bay USB controller."""

    VERSION = 2

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Create the USB-controller entry."""
        if self._async_current_entries():
            return self.async_abort(
                reason="single_instance_allowed"
            )

        await self.async_set_unique_id(
            f"{DEFAULT_VENDOR_ID:04X}:{DEFAULT_PRODUCT_ID:04X}"
        )
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Mort Bay Smart USB Wireless Controller",
                data={
                    "vendor_id": DEFAULT_VENDOR_ID,
                    "product_id": DEFAULT_PRODUCT_ID,
                },
            )

        return self.async_show_form(
            step_id="user",
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: ConfigEntry,
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported child-device types."""
        return {
            SUBENTRY_TYPE_SOCKET: SocketSubentryFlowHandler,
        }


class SocketSubentryFlowHandler(ConfigSubentryFlow):
    """Add or edit a Smart Wireless Socket."""

    def __init__(self) -> None:
        """Initialize the socket flow."""
        self._socket_name = DEFAULT_SOCKET_NAME
        self._id_mode = ID_MODE_RANDOM

    def _existing_device_ids(self) -> set[str]:
        """Return RF IDs already used by this controller."""
        entry = self._get_entry()

        return {
            str(subentry.data[CONF_DEVICE_ID]).upper()
            for subentry in entry.subentries.values()
            if (
                subentry.subentry_type == "socket"
                and CONF_DEVICE_ID in subentry.data
            )
        }

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """Add a socket."""
        if user_input is not None:
            self._socket_name = user_input[CONF_NAME].strip()
            self._id_mode = user_input[CONF_ID_MODE]

            if self._id_mode == ID_MODE_MANUAL:
                return await self.async_step_manual_id()

            device_id = generate_device_id(
                self._existing_device_ids()
            )

            return self.async_create_entry(
                title=self._socket_name,
                data={
                    CONF_NAME: self._socket_name,
                    CONF_DEVICE_ID: device_id,
                },
                unique_id=device_id,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=DEFAULT_SOCKET_NAME,
                    ): TextSelector(
                        TextSelectorConfig()
                    ),
                    vol.Required(
                        CONF_ID_MODE,
                        default=ID_MODE_RANDOM,
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=ID_MODE_RANDOM,
                                    label="Generate a random ID",
                                ),
                                SelectOptionDict(
                                    value=ID_MODE_MANUAL,
                                    label="Specify an ID",
                                ),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_manual_id(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> SubentryFlowResult:
        """Collect a manually assigned RF ID."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                device_id = normalise_device_id(
                    user_input[CONF_DEVICE_ID]
                )
            except ValueError:
                errors[CONF_DEVICE_ID] = "invalid_device_id"
            else:
                if device_id in self._existing_device_ids():
                    errors[CONF_DEVICE_ID] = (
                        "device_id_already_exists"
                    )
                else:
                    return self.async_create_entry(
                        title=self._socket_name,
                        data={
                            CONF_NAME: self._socket_name,
                            CONF_DEVICE_ID: device_id,
                        },
                        unique_id=device_id,
                    )

        return self.async_show_form(
            step_id="manual_id",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICE_ID
                    ): TextSelector(
                        TextSelectorConfig()
                    )
                }
            ),
            errors=errors,
        )
