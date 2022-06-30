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
# Public Impors
# -----------------------------------------------------------------------------

from netcad.checks import CheckResultsCollection, CheckResult, CheckStatus

from netcad.topology.checks.check_device_info import (
    DeviceInformationCheckCollection,
    DeviceInformationCheckResult,
)

# -----------------------------------------------------------------------------
# Private Improts
# -----------------------------------------------------------------------------

from netcam_aionxapi.nxapi_dut import NXAPIDeviceUnderTest

# -----------------------------------------------------------------------------
# Exports (None)
# -----------------------------------------------------------------------------

__all__ = ()

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


@NXAPIDeviceUnderTest.execute_checks.register
async def nxapi_check_device_info(
    self, device_checks: DeviceInformationCheckCollection
) -> CheckResultsCollection:
    """
    The check executor to validate the device information.  Presently this
    function validates the product-model value.
    """

    dut: NXAPIDeviceUnderTest = self
    ver_info = dut.version_info
    results = list()

    # check the product model for a match.  The actual product model may be a
    # "front" or "rear" designation.  We'll ignore those for comparison
    # purposes.

    check = device_checks.checks[0]
    result = DeviceInformationCheckResult(device=dut.device, check=check)
    msrd = result.measurement

    # check the product model, but discount any of the "front-back" designation

    exp_product_model = check.expected_results.product_model

    dev_hw = await dut.nxapi.cli("show hardware")
    hw_row = dut.dig(dev_hw, "TABLE_slot.ROW_slot.TABLE_slot_info.ROW_slot_info.0")

    msrd.product_model = has_model = hw_row["model_num"]

    check_len = min(len(has_model), len(exp_product_model))
    model_match = has_model[:check_len] == exp_product_model[:check_len]

    def on_mismatch(_field, _expd, _msrd):
        return CheckStatus.PASS if model_match else CheckStatus.FAIL

    results.append(result.measure(on_mismatch=on_mismatch))

    # include an information block that provides the raw "show version" object content.

    info = CheckResult(
        device=dut.device,
        check=check,
        status=CheckStatus.INFO,
        measurement=ver_info["rr_sys_ver"],
    )

    results.append(info)

    return results
