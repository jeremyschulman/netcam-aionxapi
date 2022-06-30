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
# System Imports
# -----------------------------------------------------------------------------

from typing import Set, Dict

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from netcad.topology.checks.check_transceivers import (
    TransceiverCheckCollection,
    TransceiverCheckResult,
    TransceiverExclusiveListCheck,
    TransceiverExclusiveListCheckResult,
)
from netcad.topology import transceiver_model_matches, transceiver_type_matches

from netcad.device import Device, DeviceInterface
from netcad.checks import CheckResultsCollection, CheckStatus

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
async def nxapi_check_transceivers(
    dut, check_collection: TransceiverCheckCollection
) -> CheckResultsCollection:
    """
    This method is imported into the NX-OS NXAPI DUT class definition to
    support checking the status of the transceivers.
    """

    dut: NXAPIDeviceUnderTest
    device = dut.device

    cli_ifxcvr_data = await dut.nxapi.cli("show interface transceiver")

    map_ifxcvr_status = {
        ifxcvr["interface"]: ifxcvr
        for ifxcvr in cli_ifxcvr_data["TABLE_interface"]["ROW_interface"]
    }

    # keep a set of the interface port numbers defined in the test cases so that
    # we can match that against the exclusive list vs. the transceivers in the
    # inventory.

    expd_ports_set = set()

    results = list()

    # first run through each of the per interface test cases ensuring that the
    # expected transceiver type and model are present.  While doing this keep
    # track of the interfaces port-numbers so that we can compare them to the
    # eclusive list.

    rsvd_ports_set = set()

    for check in check_collection.checks:
        result = TransceiverCheckResult(device=device, check=check)

        if_name = check.check_id()
        dev_iface: DeviceInterface = device.interfaces[if_name]

        if_xcvr_status = map_ifxcvr_status.get(if_name)

        if dev_iface.profile.is_reserved:
            result.status = CheckStatus.INFO
            result.logs.INFO("reserved", dict(status=if_xcvr_status))
            results.append(result.measure())
            rsvd_ports_set.add(if_name)
            continue

        expd_ports_set.add(if_name)

        _check_one_interface(
            result=result, if_xcvr_status=if_xcvr_status, results=results
        )

    # next add the test coverage for the exclusive list.
    if check_collection.exclusive:
        _check_exclusive_list(
            device=device,
            expd_ports=expd_ports_set,
            msrd_ports=map_ifxcvr_status,
            rsvd_ports=rsvd_ports_set,
            results=results,
        )

    return results


# -----------------------------------------------------------------------------
#
#                            PRIVATE CODE BEGINS
#
# -----------------------------------------------------------------------------


def _check_exclusive_list(
    device: Device,
    expd_ports: Set,
    msrd_ports: Dict[str, dict],
    rsvd_ports: Set,
    results: CheckResultsCollection,
):
    """
    Check to ensure that the list of transceivers found on the device matches the exclusive list.
    This check helps to find "unused" optics; or report them so that a Designer can account for them
    in the design-notes.
    """

    check = TransceiverExclusiveListCheck(expected_results=expd_ports)

    used_msrd_ports = set(msrd_ports)

    # remove the reserved ports form the used list so that we do not consider
    # them as part of the exclusive list testing.

    used_msrd_ports -= rsvd_ports

    result = TransceiverExclusiveListCheckResult(
        device=device, check=check, measurement=used_msrd_ports
    )

    results.append(result.measure())


def _check_one_interface(
    result: TransceiverCheckResult,
    if_xcvr_status: dict,
    results: CheckResultsCollection,
):
    """
    This function validates that a specific interface is using the specific
    transceiver as defined in the design.
    """

    # if there is no entry for this interface, then the transceiver does not
    # exist.

    if not if_xcvr_status:
        result.measurement = None
        results.append(result.measure())
        return

    msrd = result.measurement

    # if there is no model value, then the transceiver does not exist.

    msrd.model = if_xcvr_status.get("cisco_product_id")
    msrd.type = if_xcvr_status["type"].upper()

    def on_mismatch(_field, _expd, _msrd):
        match _field:
            case "model":
                is_ok = transceiver_model_matches(
                    expected_model=_expd, given_mdoel=_msrd
                )
            case "type":
                is_ok = transceiver_type_matches(expected_type=_expd, given_type=_msrd)
            case _:
                is_ok = False

        return CheckStatus.PASS if is_ok else CheckStatus.FAIL

    results.append(result.measure(on_mismatch=on_mismatch))
