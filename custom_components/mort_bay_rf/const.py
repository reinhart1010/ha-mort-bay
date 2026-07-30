"""Constants for the Mort Bay RF integration."""

from typing import Final

DOMAIN: Final = "mort_bay_rf"

PLATFORMS: Final = ["switch"]

CONF_PLUGS: Final = "plugs"
CONF_DEVICE_ID: Final = "device_id"

DEFAULT_VENDOR_ID: Final = 0x0C45
DEFAULT_PRODUCT_ID: Final = 0x7463

# Commands observed from the manufacturer's application.
COMMAND_ON: Final = 0x88
COMMAND_OFF: Final = 0x08

# Some variants reportedly accept:
# ON:  0x88 or 0xB8
# OFF: 0x08 or 0x38
