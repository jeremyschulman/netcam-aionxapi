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

from typing import Optional, Tuple
from dataclasses import dataclass

# -----------------------------------------------------------------------------
# Public Imports
# -----------------------------------------------------------------------------

from httpx import BasicAuth

# -----------------------------------------------------------------------------
# Private Imports
# -----------------------------------------------------------------------------

from .nxos_plugin_config import NXOSPluginConfig

# -----------------------------------------------------------------------------
# Exports
# -----------------------------------------------------------------------------

__all__ = ["g_nxos"]


@dataclass
class NXOSGlobals:
    """
    Define a class to encapsulate the global variables used by this plugin.

    Attributes
    ----------
    config: dict
        This is the plugin configuration dictionary as declared in the User
        `netcad.toml` configuration file.
    """

    config: Optional[NXOSPluginConfig] = None
    auth_read: Optional[Tuple[str, str]] = None
    auth_admin: Optional[Tuple[str, str]] = None
    basic_auth_read: Optional[BasicAuth] = None


# -----------------------------------------------------------------------------
# Globals
# -----------------------------------------------------------------------------

# the global variables used by this plugin
g_nxos = NXOSGlobals()
