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

from pydantic import ValidationError
from httpx import BasicAuth

from .nxos_plugin_config import NXOSPluginConfig
from .nxos_plugin_globals import g_nxos


def nxos_plugin_config(config: dict):
    """
    Called during plugin init, this function is used to set up the default
    credentials to access the IOS-XE devices.

    Parameters
    ----------
    config: dict
        The dict object as defined in the User configuration file.
    """

    try:
        g_nxos.config = NXOSPluginConfig.parse_obj(config)
    except ValidationError as exc:
        raise RuntimeError(f"Failed to load IOS-XE plugin configuration: {str(exc)}")

    auth_read = g_nxos.config.env.read

    g_nxos.auth_read = (
        auth_read.username.get_secret_value(),
        auth_read.password.get_secret_value(),
    )

    g_nxos.basic_auth_read = BasicAuth(
        username=g_nxos.auth_read[0], password=g_nxos.auth_read[1]
    )

    # If the User provides the admin credential environment variobles, then set
    # up the admin authentication that is used for configruation management

    if admin := g_nxos.config.env.admin:
        admin_user = admin.username.get_secret_value()
        admin_passwd = admin.password.get_secret_value()
        g_nxos.auth_admin = (admin_user, admin_passwd)
