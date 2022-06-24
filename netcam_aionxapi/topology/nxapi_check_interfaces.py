#  Copyright 2021 Jeremy Schulman
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

import re
from typing import Set, List, Iterable, Dict
from itertools import chain
from operator import attrgetter

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from lxml.etree import ElementBase
from pydantic import BaseModel

from netcad.device import Device, DeviceInterface
from netcad.netcam import any_failures
from netcad.checks import check_result_types as tr

from netcad.topology.checks.check_interfaces import (
    InterfaceCheckExclusiveList,
    InterfacesListExpected,
    InterfaceCheckCollection,
    InterfaceCheck,
)

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from netcam_aionxapi.nxapi_dut import NXAPIDeviceUnderTest

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = []


# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------

_match_svi = re.compile(r"Vlan(\d+)").match


@NXAPIDeviceUnderTest.execute_checks.register
async def nxapi_check_interfaces(
    dut, collection: InterfaceCheckCollection
) -> tr.CheckResultsCollection:
    """
    This async generator is responsible for implementing the "interfaces" test
    cases for NX-OS NXAPI devices.

    Parameters
    ----------
    dut: <!LEAVE UNHINTED!>
        The DUT instance for the device

    collection: InterfaceCheckCollection
        The testcases instance that contains the specific testing details.

    Yields
    ------
    TestCasePass, TestCaseFailed
    """

    dut: NXAPIDeviceUnderTest
    device = dut.device
    results = list()

    e_sh_ifaces, e_sh_vlan, e_sh_ipinf = await dut.nxapi.cli(
        commands=[
            "show interface status",
            "show vlan brief",
            "show ip interface brief vrf all",
        ],
        ofmt="xml",
    )

    # -------------------------------------------------------------------------
    # create an interface map by interface-name
    # -------------------------------------------------------------------------

    map_if_oper_data = {
        e_iface.findtext("interface"): e_iface
        for e_iface in e_sh_ifaces.xpath("TABLE_interface/ROW_interface")
    }

    # -------------------------------------------------------------------------
    # create an VLAN map by VLAN-ID (as string)
    # -------------------------------------------------------------------------

    map_svi_oper_data = {
        e_vlan.findtext("vlanshowbr-vlanid"): e_vlan
        for e_vlan in e_sh_vlan.xpath("TABLE_vlanbriefxbrief/ROW_vlanbriefxbrief")
    }

    # -------------------------------------------------------------------------
    # create an IP interface map by interface-name.  These naems are
    # 'short-names', for example "Eth1/1" rather than "Ethernet1/1". ffs.
    # -------------------------------------------------------------------------

    map_ip_ifaces = {}
    for e_intf in e_sh_ipinf.xpath("TABLE_intf/ROW_intf"):
        intf_name = e_intf.findtext("intf-name")
        intf_name = dut.expand_inteface_name(intf_name)
        map_ip_ifaces[intf_name] = e_intf

    # -------------------------------------------------------------------------
    # Check for the exclusive set of interfaces expected vs actual.
    # -------------------------------------------------------------------------

    if collection.exclusive:
        results.extend(
            _check_exclusive_interfaces_list(
                device=device,
                expd_interfaces=set(check.check_id() for check in collection.checks),
                msrd_interfaces=set(chain(map_if_oper_data, map_ip_ifaces)),
            )
        )

    _check_each_interface(
        device=dut.device,
        checks=collection.checks,
        dev_ifoper_data=map_if_oper_data,
        dev_svi_data=map_svi_oper_data,
        dev_ip_data=map_ip_ifaces,
        results=results,
    )

    return results


def _check_each_interface(
    device: Device,
    checks: List[InterfaceCheck],
    dev_svi_data: Dict[str, ElementBase],
    dev_ip_data: Dict[str, ElementBase],
    dev_ifoper_data: Dict[str, ElementBase],
    results: tr.CheckResultsCollection,
):
    # -------------------------------------------------------------------------
    # Check each interface for health checks
    # -------------------------------------------------------------------------

    for check in checks:

        if_name = check.check_id()

        # ---------------------------------------------------------------------
        # if the interface is an SVI, that is begins with "Vlan", then we need
        # to examine it differently since it does not show up in the "show
        # interfaces ..." command.
        # ---------------------------------------------------------------------

        if vlan_mo := _match_svi(if_name):

            # extract the VLAN ID value from the interface name; the lookup is
            # an int-as-string since that is how the data is encoded in the CLI
            # response object.

            vlan_id = vlan_mo.group(1)
            svi_oper_status = dev_svi_data.get(vlan_id)

            # If the VLAN does not exist then the "interface Vlan<N>" does not
            # exist on the device.

            if svi_oper_status is None:
                results.append(tr.CheckFailNoExists(device=device, check=check))
                continue

            results.extend(
                _check_one_svi(
                    device=device, check=check, svi_oper_status=svi_oper_status
                )
            )

            # done with Vlan interface, go to next test-case
            continue

        # ---------------------------------------------------------------------
        # If the interface is a Loopback ...
        # ---------------------------------------------------------------------

        if if_name.startswith("Loopback"):
            if (lo_status := dev_ip_data.get(if_name)) is None:
                results.append(tr.CheckFailNoExists(device=device, check=check))
                continue

            results.extend(
                _check_one_loopback(
                    device=device, check=check, ifip_oper_status=lo_status
                )
            )

            # done with Loopback, go to next test-case
            continue

        # ---------------------------------------------------------------------
        # The interface is not an SVI, look into the "show interfaces ..."
        # output. if the interface does not exist on the device, then the test
        # fails, and we go onto the next text.
        # ---------------------------------------------------------------------

        if (iface_oper_status := dev_ifoper_data.get(if_name)) is None:
            results.append(tr.CheckFailNoExists(device=device, check=check))

        results.extend(
            _check_one_interface(
                device=device,
                check=check,
                iface_oper_status=iface_oper_status,
            )
        )

    return results


# -----------------------------------------------------------------------------
#
#                       PRIVATE CODE BEGINS
#
# -----------------------------------------------------------------------------


def sorted_by_name(device: Device, if_name_list: Iterable[str]) -> List[str]:
    return [
        iface.name
        for iface in (
            DeviceInterface(if_name, interfaces=device.interfaces)
            for if_name in if_name_list
        )
    ]


def _check_exclusive_interfaces_list(
    device: Device, expd_interfaces: Set[str], msrd_interfaces: Set[str]
) -> tr.CheckResultsCollection:
    """
    This check validates the exclusive list of interfaces found on the device
    against the expected list in the design.
    """

    tc = InterfaceCheckExclusiveList(
        expected_results=InterfacesListExpected(if_name_list=list(expd_interfaces))
    )

    expd_sorted_names = sorted_by_name(device, expd_interfaces)

    results = list()

    if missing_interfaces := expd_interfaces - msrd_interfaces:

        results.append(
            tr.CheckFailMissingMembers(
                device=device,
                check=tc,
                field="interfaces",
                expected=expd_sorted_names,
                missing=sorted_by_name(device, missing_interfaces),
            )
        )

    if extra_interfaces := msrd_interfaces - expd_interfaces:
        results.append(
            tr.CheckFailExtraMembers(
                device=device,
                check=tc,
                field="interfaces",
                expected=expd_sorted_names,
                extras=sorted_by_name(device, extra_interfaces),
            )
        )

    if not any_failures(results):
        results.append(
            tr.CheckPassResult(
                device=device,
                check=tc,
                measurement="OK: no extra or missing interfaces",
            )
        )

    return results


# -----------------------------------------------------------------------------
# EOS Measurement dataclass
# -----------------------------------------------------------------------------


class NXAPIInterfaceMeasurement(BaseModel):
    """
    This dataclass is used to store the values as retrieved from the EOS device
    into a set of attributes that align to the test-case.
    """

    used: bool
    oper_up: bool
    desc: str
    speed: int

    _MAP_SPEED = {"1000": 1_000, "10G": 10_000, "40G": 40_000, "100G": 100_000}

    @classmethod
    def from_cli(cls, cli_payload: ElementBase):
        """returns an EOS specific measurement mapping the CLI object fields"""
        return cls(
            used=cli_payload.findtext("state") != "disabled",
            oper_up=cli_payload.findtext("state") == "connected",
            desc=cli_payload.findtext("name") or "",
            speed=NXAPIInterfaceMeasurement._MAP_SPEED.get(
                cli_payload.findtext("speed"), 0
            ),
        )


def _check_one_interface(
    device: Device, check: InterfaceCheck, iface_oper_status: ElementBase
) -> tr.CheckResultsCollection:
    """
    Validates a specific physical interface against the expectations in the
    design.
    """

    # transform the CLI data into a measurment instance for consistent
    # comparison with the expected values.

    measurement = NXAPIInterfaceMeasurement.from_cli(iface_oper_status)
    should_oper_status = check.expected_results
    if_flags = check.check_params.interface_flags or {}
    is_reserved = if_flags.get("is_reserved", False)
    results = list()

    # -------------------------------------------------------------------------
    # If the interface is marked as reserved, then report the current state in
    # an INFO report and done with this test-case.
    # -------------------------------------------------------------------------

    if is_reserved:
        results.append(
            tr.CheckInfoLog(
                device=device,
                check=check,
                field="is_reserved",
                measurement=measurement.dict(),
            )
        )
        return results

    # -------------------------------------------------------------------------
    # Check the 'used' status.  Then if the interface is not being used, then no
    # more checks are required.
    # -------------------------------------------------------------------------

    if should_oper_status.used != measurement.used:
        results.append(
            tr.CheckFailFieldMismatch(
                device=device,
                check=check,
                field="used",
                measurement=measurement.used,
            )
        )

    if not should_oper_status.used:
        return results

    # -------------------------------------------------------------------------
    # Interface is USED ... check other attributes
    # -------------------------------------------------------------------------

    field_fails = {}

    for field in ("oper_up", "desc", "speed"):

        # if a field is not present in the testcase, then we will skip it. this
        # is true for when `oper_up` is not present when the interface is marked
        # as "is_reserved=True".

        if not (exp_val := getattr(should_oper_status, field)):
            continue

        msrd_val = getattr(measurement, field)

        if exp_val == msrd_val:
            continue

        field_fails[field] = tr.CheckFailFieldMismatch(
            device=device,
            check=check,
            measurement=msrd_val,
            field=field,
            expected=check.expected_results.dict(),
        )

    # if the operational state is down, then we do not need to report failures
    # on speed.

    if "oper_up" in field_fails:
        field_fails.pop("speed", None)

    if field_fails:
        results.extend(field_fails.values())

    if not any_failures(results):
        results.append(
            tr.CheckPassResult(
                device=device, check=check, measurement=measurement.dict()
            )
        )

    return results


def _check_one_loopback(
    device: Device, check: InterfaceCheck, ifip_oper_status: ElementBase
) -> tr.CheckResultsCollection:
    """
    If the loopback interface exists (previous checked), then no other field
    checks are performed.  Yield this as a passing test-case and record the
    measured values from the device.
    """

    key_val = attrgetter("tag", "text")
    return [
        tr.CheckPassResult(
            device=device,
            check=check,
            measurement=dict(map(key_val, ifip_oper_status.iterchildren())),
        )
    ]


def _check_one_svi(
    device: Device, check: InterfaceCheck, svi_oper_status: ElementBase
) -> tr.CheckResultsCollection:
    """
    Checks the device state for a VLAN interface against the expected values in
    the design.
    """
    results = list()

    # -------------------------------------------------------------------------
    # check the vlan 'name' field, as that should match the test case
    # description field.
    # -------------------------------------------------------------------------

    msrd_desc = svi_oper_status.findtext("vlanshowbr-vlanname")
    expd_desc = check.expected_results.desc

    if msrd_desc != expd_desc:
        results.append(
            tr.CheckFailFieldMismatch(
                device=device, check=check, field="desc", measurement=msrd_desc
            )
        )

    # -------------------------------------------------------------------------
    # check the status field to match it to the expected is operational enabled
    # / disabled value.
    # -------------------------------------------------------------------------

    msrd_status = svi_oper_status.findtext("vlanshowbr-vlanstate")
    expd_status = check.expected_results.oper_up

    if expd_status != (msrd_status == "active"):
        results.append(
            tr.CheckFailFieldMismatch(
                device=device,
                check=check,
                field="oper_up",
                measurement=msrd_status,
            )
        )

    # -------------------------------------------------------------------------
    # All checks passeed !
    # -------------------------------------------------------------------------

    if not any_failures(results):
        results.append(
            tr.CheckPassResult(
                device=device,
                check=check,
                measurement=check.expected_results.dict(),
            )
        )

    return results
