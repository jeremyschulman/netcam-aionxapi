#  Copyright 2023 Jeremy Schulman
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from typing import Optional
import re

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.device import Device
from netcad.netcam.dev_config import AsyncDeviceConfigurable

# -----------------------------------------------------------------------------
# Privae Imports
# -----------------------------------------------------------------------------

from netcam_aionxapi.nxos_aiossh import NXOSAsyncSSHDriver
from netcam_aionxapi.nxos_plugin_globals import g_nxos

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["NXOSDeviceConfigurable"]


_Caps = AsyncDeviceConfigurable.Capabilities

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


class NXOSDeviceConfigurable(AsyncDeviceConfigurable):
    DEFAULT_CAPABILITIES = _Caps.diff | _Caps.rollback | _Caps.replace

    def __init__(self, *, device: Device, **_kwargs):
        """
        Initialize the instance with eAPI
        Parameters
        ----------
        device:
            The netcad device instance from the design.
        """
        super().__init__(device=device)
        username, password = g_nxos.auth_admin
        self.ssh = NXOSAsyncSSHDriver(
            device=device, username=username, password=password
        )
        self.capabilities = self.DEFAULT_CAPABILITIES
        self._scp_creds = (username, password)

    def _set_config_id(self, name: str):
        pass

    async def setup(self):
        await self.ssh.cli.open()

    async def teardown(self):
        await self.ssh.cli.close()

    async def is_reachable(self) -> bool:
        """
        Returns True when the device is reachable for config purposes; False
        otherwise.
        """
        return await self.ssh.is_available()

    async def config_get(self) -> str:
        resp = await self.ssh.cli.send_command("show running-config")
        return resp.result

    async def config_cancel(self):
        pass

    async def config_check(self, replace: Optional[bool | None] = None):
        raise RuntimeError("NX-OS does not support config-check")

    async def config_diff(self) -> str:
        resp = await self.ssh.cli.send_command(
            f"show archive config differences flash:{self.config_file.name}"
        )
        self.config_diff_contents = resp.result
        return self.config_diff_contents

    async def config_replace(self, rollback_timeout: int):
        # get the config difference before the config is applied since that is
        # the way IOS-XE operates.

        await self.config_diff()

        resp = await self.ssh.cli.send_command(
            f"configure replace flash:{self.config_file.name} "
            f"force revert trigger error timer {rollback_timeout}"
        )

        # if there is an error in the config, then raise the exception.
        # IOS-XE will revert the config based on the time.

        if re.search(r"fail|abort|error", resp.result, flags=re.I):
            raise RuntimeError(
                f"{self.device.name}: FAIL: config-replace: {resp.result}"
            )

        # otherwise the configuration is good, and confirm it now.from
        await self.ssh.cli.send_command("configure confirm")

    async def config_merge(self, rollback_timeout: int):
        raise RuntimeError("NX-OS config-merge not supported at this time.")

    async def file_delete(self):
        """
        This function is used to remove the configuration file that was
        previously copied to the remote device.  This function is expected to
        be called during a "cleanup" process.
        """
        await self.ssh.cli.send_command(f"delete /force flash:{self.config_file.name}")
