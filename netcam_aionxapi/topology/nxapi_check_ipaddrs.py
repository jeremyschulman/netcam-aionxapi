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

from typing import Sequence, Dict

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from lxml.etree import ElementBase

from netcad.topology.checks.check_ipaddrs import (
    IPInterfacesCheckCollection,
    IPInterfaceCheckResult,
    IPInterfaceExclusiveListCheck,
    IPInterfaceExclusiveListCheckResult,
)

from netcad.device import Device, DeviceInterface
from netcad.checks import CheckResultsCollection

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from ..nxapi_dut import NXAPIDeviceUnderTest


# -----------------------------------------------------------------------------
# Exports (None)
# -----------------------------------------------------------------------------

__all__ = []

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


@NXAPIDeviceUnderTest.execute_checks.register
async def nxapi_test_ipaddrs(
    dut, collection: IPInterfacesCheckCollection
) -> CheckResultsCollection:
    """
    This check executor validates the IP addresses used on the device against
    those that are defined in the design.
    """

    dut: NXAPIDeviceUnderTest
    device = dut.device
    e_dev_data = await dut.nxapi.cli("show ip interface vrf all", ofmt="xml")

    # create an IP interface map using the interface-name as the key.  The
    # interface name is not always cased correctly, for example "Loopback0" is
    # reported as "loopback0". so title the value when storing the key.

    map_ip_ifaces: Dict[str, ElementBase] = {}
    for e_row_intf in e_dev_data.xpath("TABLE_intf/ROW_intf"):
        intf_name: str = e_row_intf.findtext("intf-name")
        map_ip_ifaces[intf_name.title()] = e_row_intf

    results = list()
    if_names = list()

    for check in collection.checks:
        result = IPInterfaceCheckResult(device=device, check=check)

        if_name = check.check_id()
        if_names.append(if_name)

        if (e_if_ip_data := map_ip_ifaces.get(if_name)) is None:
            result.measurement = None
            results.append(result.measure())
            continue

        await _check_one_interface(
            dut=dut, result=result, msrd_data=e_if_ip_data, results=results
        )

    # TODO: implement the exclusive check
    return results


# -----------------------------------------------------------------------------


async def _check_one_interface(
    dut: NXAPIDeviceUnderTest,
    result: IPInterfaceCheckResult,
    msrd_data: ElementBase,
    results: CheckResultsCollection,
):
    """
    This function validates a specific interface use of an IP address against
    the design expectations.
    """

    check = result.check
    expd_if_ipaddr = check.expected_results.if_ipaddr
    msrd = result.measurement

    # get the interface name being tested
    if_name = check.check_id()

    msrd_if_addr = msrd_data.findtext("prefix")
    msrd.if_ipaddr = f"{msrd_if_addr}/{msrd_data.findtext('masklen')}"

    # if the design indicates the interfae is reserved, then pass the
    # check and note this in the logs

    if expd_if_ipaddr == "is_reserved":
        result.logs.INFO("reserved", dict(measured=msrd_if_addr))
        results.append(result)
        return

    # -------------------------------------------------------------------------
    # Ensure the IP interface is "up".
    # TODO: should check if the interface is enabled before presuming this
    #       up condition check.
    # -------------------------------------------------------------------------

    # check to see if the interface is disabled before we check to see if the IP
    # address is in the up condition.

    dut_interfaces = dut.device_info["interfaces"]
    dut_iface = dut_interfaces[if_name]
    iface_enabled = dut_iface["enabled"] is True

    has_if_oper = msrd_data.findtext("proto-state")
    msrd.oper_up = has_if_oper == "up"

    # if the interface is an SVI, then we need to check to see if _all_ of the
    # associated physical interfaces are either disabled or in a reseverd
    # condition.

    if iface_enabled and not msrd.oper_up and if_name.startswith("Vlan"):
        # updates the result
        await _check_vlan_assoc_interface(
            dut,
            result=result,
            if_name=if_name,
            msrd_ipifaddr_oper=has_if_oper,
        )
        results.append(result)
        return

    # normal interface conditions, so measure before adding.
    results.append(result.measure())


def _test_exclusive_list(
    device: Device,
    expd_if_names: Sequence[str],
    msrd_if_names: Sequence[str],
    results: CheckResultsCollection,
):
    """
    This check determines if there are any extra IP Interfaces defined on the
    device that are not expected per the design.
    """

    def sorted_by(if_name: str):
        return DeviceInterface(if_name, interfaces=device.interfaces)

    result = IPInterfaceExclusiveListCheckResult(
        device=device,
        check=IPInterfaceExclusiveListCheck(expected_results=expd_if_names),
        measurement=sorted(msrd_if_names, key=sorted_by),
    )

    results.append(result.measure())


async def _check_vlan_assoc_interface(
    dut: NXAPIDeviceUnderTest,
    result: IPInterfaceCheckResult,
    if_name: str,
    msrd_ipifaddr_oper: str,
):
    """
    This function is used to check whether a VLAN SVI ip address is not "up"
    due to the fact that the underlying interfaces are either disabled or in a
    "reserved" design; meaning we do not care if they are up or down. If the
    SVI is down because of this condition, the test case will "pass", and an
    information record is yielded to inform the User.

    Parameters
    ----------
    dut:
        The device under test

    result:
        The result instance for the given check

    if_name:
        The specific VLAN SVI name, "Vlan12" for example:

    msrd_ipifaddr_oper:
        The measured opertional state of the IP interface

    Yields
    ------
    netcad test case results; one or more depending on the condition of SVI
    interfaces.
    """
    vlan_id = if_name.split("Vlan")[-1]
    cli_res = await dut.nxapi.cli(f"show vlan id {vlan_id}")

    # the interface list is stored as a CSV, so unwind that into a set of interface-names
    vlan_cfgd_ifnames = set(
        cli_res["TABLE_vlanbriefid"]["ROW_vlanbriefid"]["vlanshowplist-ifidx"].split(
            ","
        )
    )
    disrd_ifnames = set()
    dut_ifs = dut.device_info["interfaces"]

    for check_ifname in vlan_cfgd_ifnames:
        dut_iface = dut_ifs[check_ifname]
        if (dut_iface["enabled"] is False) or (
            "is_reserved" in dut_iface["profile_flags"]
        ):
            disrd_ifnames.add(check_ifname)

    # if all the interfaces in the VLAN are mared as "reserved" in the
    # design, then mark this check as a PASS, and log some information.

    if disrd_ifnames == vlan_cfgd_ifnames:
        result.logs.INFO(
            "oper_up",
            dict(
                if_oper=msrd_ipifaddr_oper,
                interfaces=list(vlan_cfgd_ifnames),
                message="interfaces are either disabled or in reserved state",
            ),
        )

        # pass this check, do not call .measure
        return

    # measure the results and return
    result.measure()
