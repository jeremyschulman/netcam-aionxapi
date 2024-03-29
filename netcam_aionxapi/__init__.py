#  Copyright 2022 Jeremy Schulman
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

import importlib.metadata as importlib_metadata

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.device import Device

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from . import nxapi_dut
from .nxapi_dut import NXAPIDeviceUnderTest
from .config.nxos_dcfg import NXOSDeviceConfigurable
from .nxos_plugin_init import nxos_plugin_config

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------

plugin_version = importlib_metadata.version(__name__)
plugin_description = "Cisco NX-OS NXAPI systems (asyncio)"


def plugin_get_dut(device: Device) -> NXAPIDeviceUnderTest:
    if device.os_name != "nx-os":
        raise RuntimeError(
            f"{device.name} called NX-OS dut with improper os-name: {device.os_name}"
        )

    return NXAPIDeviceUnderTest(device=device)


def plugin_get_dcfg(device: Device) -> NXOSDeviceConfigurable:
    if device.os_name != "nx-os":
        raise RuntimeError(
            f"{device.name} called NX-OS config with improper os-name: {device.os_name}"
        )

    return NXOSDeviceConfigurable(device=device)


def plugin_init(plugin_def: dict):
    if not (config := plugin_def.get("config")):
        raise RuntimeError("Missing IOS-XE driver config, please check.")

    nxos_plugin_config(config)
