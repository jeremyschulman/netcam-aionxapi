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

# =============================================================================
# This file contains the NX-OS NXAPI "Device Under Test" class definition.
# This is where the specific check-executors are wired into the class to
# support the various design-service checks.
# =============================================================================

# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

import asyncio
from typing import Optional
from functools import singledispatchmethod, reduce

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

import httpx
from lxml.etree import ElementBase
from aionxapi import Device as DeviceNXAPI

from netcad.device import Device
from netcad.checks import CheckCollection, CheckResultsCollection
from netcam.dut import AsyncDeviceUnderTest, SetupError

# -----------------------------------------------------------------------------
# Privae Imports
# -----------------------------------------------------------------------------

from .nxos_plugin_globals import g_nxos

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["NXAPIDeviceUnderTest"]


# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


class NXAPIDeviceUnderTest(AsyncDeviceUnderTest):
    """
    This class provides the Cisco NX-OS NAPI device-under-test plugin for
    directly communicating with the device via the NXAPI interface.  The
    underpinning transport is using asyncio.  Refer to the `aio-nxapi` package
    for further details.

    Attributes
    ----------
    nxapi: aionxapi.Device
        The asyncio driver instance used to communicate with the device via
        NXAPI.

    version_info: dict
        The results of 'show version' that is extracted from the device during
        the `setup` process.
    """

    def __init__(self, *, device: Device, **_kwargs):
        """DUT construction creates instance of EAPI transport"""

        super().__init__(device=device)

        # use JSON format by default
        self.nxapi = DeviceNXAPI(
            host=device.name, auth=g_nxos.basic_auth_read, timeout=60
        )
        self.nxapi.ofmt = "json"

        self.version_info: Optional[dict] = None

        # inialize the DUT cache mechanism; used exclusvely by the
        # `api_cache_get` method.

        self._api_cache_lock = asyncio.Lock()
        self._api_cache = dict()

    # -------------------------------------------------------------------------
    #
    #                       NXOS DUT Specific Methods
    #
    # -------------------------------------------------------------------------

    async def api_cache_get(
        self, command: str, key: Optional[str] = None, **kwargs
    ) -> ElementBase | dict | str:
        """
        This function is used by other class methods that want to abstract the
        collection function of a given NXAPI call so that the results of that
        call are cached and avaialble for other check executors.  This method
        should not be called outside other methods of this DUT class, but this
        is not a hard constraint.

        For example, if the result of "show interface switchport" is going to be
        used by multiple check executors, then there would exist a method in
        this class called `get_switchports` that uses this `api_cache_get`
        method.

        Parameters
        ----------
        command: str
            The actual NX-OS CLI command used to obtain the NXAPI results.  This
            value will by default be used as the cache-key.

        key: str, optional
            The cache-key string that is used to uniquely identify the contents
            of the cache.  For example 'switchports' may be the cache key to cache
            the results of the 'show interfaces switchport' command.

        Other Parameters
        ----------------
        Any keyword-args supported by the underlying eAPI Device driver; for
        example `ofmt` can be used to change the output format from the default
        of XML to text.  Refer to the aio-nxapi package for further details.

        Returns
        -------
        Either the cached data corresponding to the key if exists in the cache,
        or the newly retrieved data from the device; which is then cached for
        future use.
        """

        async with self._api_cache_lock:
            _c_key = key or command

            if (has_data := self._api_cache.get(_c_key)) is None:
                has_data = await self.nxapi.cli(command, **kwargs)
                self._api_cache[_c_key] = has_data

            return has_data

    # -------------------------------------------------------------------------
    #
    #                              DUT Methods
    #
    # -------------------------------------------------------------------------

    async def setup(self):
        """DUT setup process"""
        await super().setup()
        if not await self.nxapi.check_connection():
            raise SetupError(
                f"Unable to connect to NXAPI on device: {self.device.name}: "
                "Device offline or NXAPI is not enabled, check config."
            )

        try:
            self.version_info = await self.nxapi.cli("show version")

        except httpx.HTTPError as exc:
            rt_exc = SetupError(
                f"Unable to connect to NXAPI device {self.device.name}: {str(exc)}"
            )
            rt_exc.__traceback__ = exc.__traceback__
            await self.teardown()
            raise rt_exc

    async def teardown(self):
        """DUT tearndown process"""
        await self.nxapi.aclose()

    @staticmethod
    def dig(data: dict, spec: str):
        """
        This is a micro 'dig' function to get to a spot in a dictionary, only
        processes dictionary key-values and list-objects.

        Parameters
        ----------
        data: dict
            The source data dictionary

        spec: str
            The 'dig' spec as a string in dotted notation, for example:
            'TABLE_slot.ROW_slot.TABLE_slot_info.ROW_slot_info.0'

        Returns
        -------
        The value as the end of the dig, or None
        """

        def get(o, i):
            _get = o.__getitem__
            return _get(i) if isinstance(o, dict) else _get(int(i))

        return reduce(lambda a, i: get(a, i), spec.split("."), data)

    @staticmethod
    def expand_inteface_name(if_name: str) -> str:
        if if_name.startswith("Lo") and not if_name.startswith("Loopback"):
            return if_name.replace("Lo", "Loopback")

        if if_name.startswith("Eth") and not if_name.startswith("Ethernet"):
            return if_name.replace("Eth", "Ethernet")

        return if_name

    @singledispatchmethod
    async def execute_checks(
        self, checks: CheckCollection
    ) -> Optional[CheckResultsCollection]:
        """
        This method is only called when the DUT does not support a specific
        design-service check.  This function *MUST* exist so that the supported
        checks can be "wired into" this class using the dispatch register mechanism.
        """
        return super().execute_checks()
