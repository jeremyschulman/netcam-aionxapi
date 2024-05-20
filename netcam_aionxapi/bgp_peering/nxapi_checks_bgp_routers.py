# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from lxml.etree import ElementBase

from netcad.bgp_peering.checks import (
    BgpRoutersCheckCollection,
    BgpRouterCheck,
    BgpRouterCheckResult,
)

from netcad.checks import CheckResultsCollection

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from ..nxapi_dut import NXAPIDeviceUnderTest
from .nxapi_check_bgp_peering_defs import DEFAULT_VRF_NAME

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


@NXAPIDeviceUnderTest.execute_checks.register
async def check_bgp_neighbors(
    self, check_bgp_routers: BgpRoutersCheckCollection
) -> CheckResultsCollection:
    """
    This function is responsible for validating the NXOS device IP BGP neighbors
    are operationally correct.

    Parameters
    ----------
    self: NXOSDeviceUnderTest
        *** DO NOT TYPEHINT because registration will fail if you do ***

    check_bgp_routers: BgpRoutersCheckCollection
        The checks associated for BGP Routers defined on the device

    Returns
    -------
    trt.CheckResultsCollection - The results of the checks
    """
    results = list()
    checks = check_bgp_routers.checks
    dut: NXAPIDeviceUnderTest = self

    dev_data = await dut.api_cache_get(command="show bgp sessions", ofmt="xml")

    for rtr_chk in checks:
        _check_router_vrf(dut=dut, check=rtr_chk, dev_data=dev_data, results=results)

    return results


# -----------------------------------------------------------------------------
#
#                                 PRIVATE CODE BEGINS
#
# -----------------------------------------------------------------------------


def _check_router_vrf(
    dut: NXAPIDeviceUnderTest,
    check: BgpRouterCheck,
    dev_data: ElementBase,
    results: CheckResultsCollection,
):
    check_vrf = check.check_params.vrf or DEFAULT_VRF_NAME

    e_bgp_spkr: ElementBase = dev_data.xpath(
        f'TABLE_vrf/ROW_vrf[vrf-name-out = "{check_vrf}"]'
    )[0]

    result = BgpRouterCheckResult(device=dut.device, check=check)
    msrd = result.measurement

    # from the device, routerId is a string
    msrd.router_id = e_bgp_spkr.findtext("router-id", default="")

    # from the device, asn is a string-int
    msrd.asn = int(e_bgp_spkr.findtext("local-as", default="0"))

    results.append(result.measure())
