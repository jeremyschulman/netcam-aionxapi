# -----------------------------------------------------------------------------
# System Imports
# -----------------------------------------------------------------------------

from types import MappingProxyType
from netcad.feats.bgp_peering import BgpNeighborState


DEFAULT_VRF_NAME = "default"

# This mapping table is used to map the NXOS Device string value reported in the
# "show" command to the BGP neighbor state Enum defined in the check expected
# value.

MAP_BGP_STATES: MappingProxyType[str, BgpNeighborState] = MappingProxyType(
    {
        "Idle": BgpNeighborState.IDLE,
        "Connect": BgpNeighborState.CONNECT,
        "Active": BgpNeighborState.ACTIVE,
        "OpenSent": BgpNeighborState.OPEN_SENT,
        "OpenConfirm": BgpNeighborState.OPEN_CONFIRM,
        "Established": BgpNeighborState.ESTABLISHED,
    }
)
