# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

import asyncio

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from scrapli.driver.core.cisco_nxos import AsyncNXOSDriver
from netcad.device import Device


class NXOSAsyncSSHDriver:
    def __init__(self, device: Device, username, password):
        self.device = device
        self.cli = AsyncNXOSDriver(
            host=device.name,
            transport="asyncssh",
            auth_username=username,
            auth_password=password,
            auth_strict_key=False,
        )

    async def is_available(self) -> bool:
        try:
            await asyncio.open_connection(host=self.device.name, port=self.cli.port)
        except Exception:  # noqa
            return False
        return True
