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
#

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.topology.checks.check_cabling_nei import (
    InterfaceCablingCheckCollection,
    InterfaceCablingCheckResult,
)
from netcad.topology.checks.utils_cabling_nei import (
    nei_interface_match,
    nei_hostname_match,
)

from netcad.checks import CheckResultsCollection, CheckStatus

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from ..nxapi_dut import NXAPIDeviceUnderTest


# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = []

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


@NXAPIDeviceUnderTest.execute_checks.register
async def nxapi_test_cabling(
    dut, testcases: InterfaceCablingCheckCollection
) -> CheckResultsCollection:
    """
    Support the "cabling" tests for Cisco NXOS devices.  These tests are
    implementeding by examing the LLDP neighborship status.

    This function is imported directly into the NXOS DUT class defintion.

    Parameters
    ----------
    dut: ** DO NOT TYPE HINT **
    testcases:
        The device specific cabling testcases as build via netcad.

    Yields
    ------
    Netcad test-case items.
    """
    dut: NXAPIDeviceUnderTest
    device = dut.device
    results = list()

    cli_lldp_rsp = await dut.nxapi.cli("show lldp neighbors")

    # create a map of local interface name to the LLDP neighbor record.

    dev_lldpnei_ifname = {
        dut.expand_inteface_name(nei["l_port_id"]): nei
        for nei in cli_lldp_rsp["TABLE_nbor"]["ROW_nbor"]
    }

    for check in testcases.checks:
        if_name = check.check_id()
        result = InterfaceCablingCheckResult(device=device, check=check)
        if not (port_nei := dev_lldpnei_ifname.get(if_name)):
            result.measurement = None
            results.append(result.measure())
            continue

        _test_one_interface(result=result, ifnei_status=port_nei, results=results)

    return results


def _test_one_interface(
    result: InterfaceCablingCheckResult,
    ifnei_status: dict,
    results: CheckResultsCollection,
):
    """
    Validates the LLDP information for a specific interface.
    """
    # expd_name = check.expected_results.device
    # expd_port_id = check.expected_results.port_id

    msrd = result.measurement
    msrd.device = ifnei_status["chassis_id"]
    msrd.port_id = ifnei_status["port_id"]

    def on_mismatch(_field, _expd, _msrd):
        is_ok = False
        match _field:
            case "device":
                is_ok = nei_hostname_match(_expd, _msrd)
            case "port_id":
                is_ok = nei_interface_match(_expd, _msrd)

        return CheckStatus.PASS if is_ok else CheckStatus.FAIL

    results.append(result.measure(on_mismatch=on_mismatch))

    return results
