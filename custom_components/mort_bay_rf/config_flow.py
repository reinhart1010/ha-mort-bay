"""Config flow for Mort Bay RF power plugs."""

from __future__ import annotations

import re
import secrets
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_DEVICE_ID,
    CONF_PLUGS,
    DEFAULT_PRODUCT_ID,
    DEFAULT_VENDOR_ID,
    DOMAIN,
)

ID_PATTERN = re.compile(r"^[0-9A-Fa-f]{4}$")

CONF_ID_MODE = "id_mode"
ID_MODE_RANDOM = "random"
ID_MODE_MANUAL = "manual"


def normalise_device_id(value: str) -> str:
    """Validate and normalise a two-byte hexadecimal ID."""
    compact = (
        value.strip()
        .replace(":", "")
        .replace("-", "")
        .replace(" ", "")
    )

    if not ID_PATTERN.fullmatch(compact):
        raise ValueError(
            "The ID must contain exactly four hexadecimal digits"
        )

    return compact.upper()


def generate_device_id(
    existing_ids: set[str] | None = None,
) -> str:
    """Generate an unused two-byte identifier."""
    existing_ids = existing_ids or set()

    # Reserve 0000 and FFFF because broadcast-like values are often
    # best avoided even when the current protocol accepts them.
    while True:
        candidate = secrets.token_hex(2).upper()
        if (
            candidate not in {"0000", "FFFF"}
            and candidate not in existing_ids
        ):
            return candidate


class MortBayRFConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a Mort Bay RF config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._plug_name: str | None = None
        self._id_mode: str | None = None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Configure the USB dongle."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Only one process should own this physical USB dongle.
        await self.async_set_unique_id(
            f"{DEFAULT_VENDOR_ID:04X}:{DEFAULT_PRODUCT_ID:04X}"
        )
        self._abort_if_unique_id_configured()

        if user_input is not None:
            self._plug_name = user_input[CONF_NAME]
            self._id_mode = user_input[CONF_ID_MODE]

            if self._id_mode == ID_MODE_MANUAL:
                return await self.async_step_manual_id()

            device_id = generate_device_id()
            return self._create_entry(
                plug_name=self._plug_name,
                device_id=device_id,
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                    default="Mort Bay Smart Wireless Socket",
                ): str,
                vol.Required(
                    CONF_ID_MODE,
                    default=ID_MODE_RANDOM,
                ): vol.In(
                    {
                        ID_MODE_RANDOM: "Generate a random ID",
                        ID_MODE_MANUAL: "Specify an ID",
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    async def async_step_manual_id(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Collect a manually selected plug ID."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                device_id = normalise_device_id(
                    user_input[CONF_DEVICE_ID]
                )
            except ValueError:
                errors[CONF_DEVICE_ID] = "invalid_device_id"
            else:
                return self._create_entry(
                    plug_name=self._plug_name or "Mort Bay Smart Power Plug",
                    device_id=device_id,
                )

        return self.async_show_form(
            step_id="manual_id",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "example": "4A7C",
            },
        )

    def _create_entry(
        self,
        *,
        plug_name: str,
        device_id: str,
    ) -> FlowResult:
        """Create the dongle entry with its first plug."""
        return self.async_create_entry(
            title="Mort Bay Smart USB Wireless Controller",
            data={
                "vendor_id": DEFAULT_VENDOR_ID,
                "product_id": DEFAULT_PRODUCT_ID,
                CONF_PLUGS: [
                    {
                        CONF_NAME: plug_name,
                        CONF_DEVICE_ID: device_id,
                    }
                ],
            },
        )
