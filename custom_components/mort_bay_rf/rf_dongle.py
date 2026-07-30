"""USB transport for Mort Bay RF power plugs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Final

import usb.core
import usb.util

from homeassistant.core import HomeAssistant

from .const import COMMAND_OFF, COMMAND_ON

_LOGGER = logging.getLogger(__name__)

USB_TIMEOUT_MS: Final = 1_000

"""
This packet suffix is required to send correct RF dongle transmission parameters.
"""
PACKET_SUFFIX = bytes([
    0x20,
    0x60,
    0x0C,
    0x18,
    0x00,
])

class RFDongleError(Exception):
    """Base RF dongle error."""


class RFDongleNotFoundError(RFDongleError):
    """Raised when the USB dongle cannot be found."""


class RFDongleCommunicationError(RFDongleError):
    """Raised when USB communication fails."""


@dataclass(slots=True, frozen=True)
class DongleAddress:
    """USB identity of the RF dongle."""

    vendor_id: int
    product_id: int


class RFDongle:
    """Control an RF USB dongle."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: DongleAddress,
    ) -> None:
        self._hass = hass
        self._address = address
        self._device: usb.core.Device | None = None
        self._endpoint_out: usb.core.Endpoint | None = None
        self._claimed_interface: int | None = None
        self._lock = asyncio.Lock()

    async def async_connect(self) -> None:
        """Open and configure the USB device."""
        async with self._lock:
            await self._hass.async_add_executor_job(self._connect)

    def _connect(self) -> None:
        """Open and claim the USB dongle synchronously."""
        if self._device is not None:
            return

        device = usb.core.find(
            idVendor=self._address.vendor_id,
            idProduct=self._address.product_id,
        )

        if device is None:
            raise RFDongleNotFoundError(
                f"USB dongle "
                f"{self._address.vendor_id:04X}:"
                f"{self._address.product_id:04X} not found"
            )

        interface_number = 0
        claimed = False
        detached_kernel_driver = False

        try:
            # The device is already configured by Linux.
            # Do not call device.set_configuration() here.
            configuration = device.get_active_configuration()

            interface = usb.util.find_descriptor(
                configuration,
                bInterfaceNumber=interface_number,
                bAlternateSetting=0,
            )

            if interface is None:
                raise RFDongleCommunicationError(
                    "USB interface 0 was not found"
                )

            try:
                if device.is_kernel_driver_active(interface_number):
                    device.detach_kernel_driver(interface_number)
                    detached_kernel_driver = True
            except NotImplementedError:
                _LOGGER.debug(
                    "Kernel-driver detection is unsupported"
                )
            except usb.core.USBError as err:
                raise RFDongleCommunicationError(
                    f"Could not detach kernel driver from "
                    f"interface {interface_number}: {err}"
                ) from err

            try:
                usb.util.claim_interface(
                    device,
                    interface_number,
                )
                claimed = True
            except usb.core.USBError as err:
                raise RFDongleCommunicationError(
                    f"Could not claim USB interface "
                    f"{interface_number}: {err}"
                ) from err

            endpoint_out = usb.util.find_descriptor(
                interface,
                custom_match=lambda endpoint: (
                    endpoint.bEndpointAddress == 0x02
                ),
            )

            if endpoint_out is None:
                raise RFDongleCommunicationError(
                    "USB interrupt OUT endpoint 0x02 was not found"
                )

            self._device = device
            self._endpoint_out = endpoint_out
            self._claimed_interface = interface_number
            self._detached_kernel_driver = detached_kernel_driver

        except Exception:
            if claimed:
                try:
                    usb.util.release_interface(
                        device,
                        interface_number,
                    )
                except usb.core.USBError:
                    pass

            if detached_kernel_driver:
                try:
                    device.attach_kernel_driver(interface_number)
                except (NotImplementedError, usb.core.USBError):
                    pass

            usb.util.dispose_resources(device)
            raise

    async def async_disconnect(self) -> None:
        """Release the USB interface."""
        async with self._lock:
            await self._hass.async_add_executor_job(self._disconnect)

    def _disconnect(self) -> None:
        """Release the USB interface synchronously."""
        if self._device is None:
            return

        try:
            if self._claimed_interface is not None:
                usb.util.release_interface(
                    self._device,
                    self._claimed_interface,
                )
        except usb.core.USBError:
            _LOGGER.debug(
                "Error releasing RF dongle interface",
                exc_info=True,
            )
        finally:
            usb.util.dispose_resources(self._device)
            self._device = None
            self._endpoint_out = None
            self._claimed_interface = None

    async def async_turn_on(self, device_id: bytes) -> None:
        """Transmit an ON command."""
        await self._async_send(device_id, COMMAND_ON)

    async def async_turn_off(self, device_id: bytes) -> None:
        """Transmit an OFF command."""
        await self._async_send(device_id, COMMAND_OFF)

    async def _async_send(
        self,
        device_id: bytes,
        command: int,
    ) -> None:
        """Serialize and transmit one RF command."""
        if len(device_id) != 2:
            raise ValueError("RF device ID must contain exactly two bytes")

        async with self._lock:
            await self._hass.async_add_executor_job(
                self._send,
                device_id,
                command,
            )

    def _send(self, device_id: bytes, command: int) -> None:
        """Send one RF command through interrupt OUT endpoint 0x02."""
        if len(device_id) != 2:
            raise ValueError(
                "RF device ID must contain exactly two bytes"
            )

        if not 0 <= command <= 0xFF:
            raise ValueError("RF command must be one byte")

        endpoint_out = self._endpoint_out

        if self._device is None or endpoint_out is None:
            raise RFDongleCommunicationError(
                "RF dongle is not connected"
            )

        payload = device_id + bytes([command]) + PACKET_SUFFIX

        try:
            written = endpoint_out.write(
                payload,
                timeout=3000,
            )
        except usb.core.USBTimeoutError as err:
            raise RFDongleCommunicationError(
                "RF dongle timed out sending packet "
                f"{payload.hex(' ').upper()}"
            ) from err
        except usb.core.USBError as err:
            raise RFDongleCommunicationError(
                f"Could not send RF command: {err}"
            ) from err

        if written != len(payload):
            raise RFDongleCommunicationError(
                f"USB short write: wrote {written} of "
                f"{len(payload)} bytes"
            )

        _LOGGER.debug(
            "Sent RF packet: %s",
            payload.hex(" ").upper(),
        )
