# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from lxml.etree import ElementBase as Element

from netcad.bgp_peering.checks import (
    BgpNeighborsCheckCollection,
    BgpNeighborCheck,
    BgpNeighborCheckResult,
)

from netcad.checks import check_result_types as trt

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from ..nxapi_dut import NXAPIDeviceUnderTest
from .nxapi_check_bgp_peering_defs import DEFAULT_VRF_NAME, MAP_BGP_STATES

# -----------------------------------------------------------------------------
#
#                                 CODE BEGINS
#
# -----------------------------------------------------------------------------


@NXAPIDeviceUnderTest.execute_checks.register
async def check_neeighbors(
    self, check_collection: BgpNeighborsCheckCollection
) -> trt.CheckResultsCollection:
    dut: NXAPIDeviceUnderTest = self

    results: trt.CheckResultsCollection = list()
    checks = check_collection.checks

    dev_data = await dut.api_cache_get(command="show bgp sessions", ofmt="xml")

    bgp_vrf_spkrs = {}
    for bgp_spkr in dev_data.xpath("TABLE_vrf/ROW_vrf"):
        vrf_name = bgp_spkr.findtext("vrf-name-out")
        bgp_vrf_spkrs[vrf_name] = bgp_spkr

    for check in checks:
        check_vrf = check.check_params.vrf or DEFAULT_VRF_NAME
        bgp_spkr: Element = bgp_vrf_spkrs[check_vrf]

        _check_bgp_neighbor(dut=dut, check=check, bgp_spkr=bgp_spkr, results=results)

    return results


# -----------------------------------------------------------------------------
#
#                                 PRIVATE CODE BEGINS
#
# -----------------------------------------------------------------------------


def _check_bgp_neighbor(
    dut: NXAPIDeviceUnderTest,
    check: BgpNeighborCheck,
    bgp_spkr: Element,
    results: trt.CheckResultsCollection,
):
    """
    This function checks one BGP neighbor.  A check is considered to pass if and
    only if:

        (1) The neighbor exists
        (2) The neighbor ASN matches expected value
        (3) The BGP state matches expected value

    Notes
    -----
    The `results` argument is appended with check results items.

    Parameters
    ----------
    dut: NXAPIDeviceUnderTest
        The instance of the DUT

    check: BgpNeighborCheck
        The instance of the specific BGP neighbor check

    bgp_spkr: Element
        The BGP speaker XML output data for the show command.

    results: trt.CheckResultsCollection
        The accumulation of check results.

    Returns
    -------
    True if the check passes, False otherwise.
    """
    result = BgpNeighborCheckResult(device=dut.device, check=check)

    params = check.check_params

    # if the neighbor for the expected remote IP does not exist, then record
    # that result, and we are done checking this neighbor.

    if not (
        found := bgp_spkr.xpath(
            f'TABLE_neighbor/ROW_neighbor[neighbor-id = "{params.nei_ip}"]'
        )
    ):
        result.measurement = None
        results.append(result.measure())
        return

    # collect measurements

    msrd = result.measurement
    nei_data: Element = found[0]

    # device stores ASN as string-int
    msrd.remote_asn = int(nei_data.findtext("remoteas"))
    msrd.state = MAP_BGP_STATES[nei_data.findtext("state")]

    results.append(result.measure())
