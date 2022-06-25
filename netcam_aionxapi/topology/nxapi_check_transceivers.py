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
    TransceiverCheck,
    TransceiverExclusiveListCheck,
)
from netcad.topology import transceiver_model_matches, transceiver_type_matches

from netcad.device import Device, DeviceInterface
from netcad.netcam import any_failures
from netcad.checks import check_result_types as trt

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
    self, check_collection: TransceiverCheckCollection
) -> trt.CheckResultsCollection:
    """
    This method is imported into the ESO DUT class definition to support
    checking the status of the transceivers.

    Notes
    -----
    On EOS platforms, the XCVR inventory is stored as port _numbers-strings_ and
    not as the interface name.  For example, "Interface54/1" is represented in
    the EOS inventor as "54".
    """

    dut: NXAPIDeviceUnderTest = self
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

        if_name = check.check_id()
        dev_iface: DeviceInterface = device.interfaces[if_name]

        if_xcvr_status = map_ifxcvr_status.get(if_name)

        if dev_iface.profile.is_reserved:
            results.append(
                trt.CheckInfoLog(
                    device=device,
                    check=check,
                    measurement=dict(
                        message="interface is in reserved state",
                        status=if_xcvr_status,
                    ),
                )
            )
            rsvd_ports_set.add(if_name)
            continue

        expd_ports_set.add(if_name)

        results.extend(
            _check_one_interface(
                device=device, check=check, if_xcvr_status=if_xcvr_status
            )
        )

    # next add the test coverage for the exclusive list.
    if check_collection.exclusive:
        results.extend(
            _check_exclusive_list(
                device=device,
                expd_ports=expd_ports_set,
                msrd_ports=map_ifxcvr_status,
                rsvd_ports=rsvd_ports_set,
            )
        )

    return results


# -----------------------------------------------------------------------------
#
#                            PRIVATE CODE BEGINS
#
# -----------------------------------------------------------------------------


def _check_exclusive_list(
    device: Device, expd_ports: Set, msrd_ports: Dict[str, dict], rsvd_ports: Set
) -> trt.CheckResultsCollection:
    """
    Check to ensure that the list of transceivers found on the device matches the exclusive list.
    This check helps to find "unused" optics; or report them so that a Designer can account for them
    in the design-notes.
    """

    results = list()
    tc = TransceiverExclusiveListCheck()

    used_msrd_ports = set(msrd_ports)

    # remove the reserved ports form the used list so that we do not consider
    # them as part of the exclusive list testing.

    used_msrd_ports -= rsvd_ports

    if missing := expd_ports - used_msrd_ports:
        results.append(
            trt.CheckFailMissingMembers(
                device=device,
                check=tc,
                field="transceivers",
                expected=sorted(expd_ports),
                missing=sorted(missing),
            )
        )

    if extras := used_msrd_ports - expd_ports:
        results.append(
            trt.CheckFailExtraMembers(
                device=device,
                check=tc,
                field="transceivers",
                expected=sorted(expd_ports),
                extras=sorted(extras),
            )
        )

    if not any_failures(results):
        results.append(
            trt.CheckPassResult(
                device=device,
                check=TransceiverExclusiveListCheck(),
                measurement="OK: no extra or missing transceivers",
            )
        )

    return results


def _check_one_interface(
    device: Device, check: TransceiverCheck, if_xcvr_status: dict
) -> trt.CheckResultsCollection:
    """
    This function validates that a specific interface is using the specific
    transceiver as defined in the design.
    """

    results = list()

    # if there is no entry for this interface, then the transceiver does not
    # exist.

    if not if_xcvr_status:
        results.append(
            trt.CheckFailNoExists(
                device=device,
                check=check,
            )
        )
        return results

    # if there is no model value, then the transceiver does not exist.

    exp_model = check.expected_results.model
    if not (msrd_model := if_xcvr_status.get("partnum")):
        results.append(
            trt.CheckFailNoExists(
                device=device,
                check=check,
            )
        )
        return results

    if not transceiver_model_matches(expected_model=exp_model, given_mdoel=msrd_model):
        results.append(
            trt.CheckFailFieldMismatch(
                device=device,
                check=check,
                field="model",
                measurement=msrd_model,
            )
        )

    # always upper-case the type value for more consistent validation checking.

    expd_type = check.expected_results.type
    msrd_type = if_xcvr_status["type"].upper()
    if not transceiver_type_matches(expected_type=expd_type, given_type=msrd_type):
        results.append(
            trt.CheckFailFieldMismatch(
                device=device, check=check, field="type", measurement=msrd_type
            )
        )

    if not any_failures(results):
        results.append(
            trt.CheckPassResult(
                device=device,
                check=check,
                measurement=dict(model=msrd_model, type=msrd_type),
            )
        )

    return results
