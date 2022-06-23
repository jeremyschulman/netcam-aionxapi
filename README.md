# NetCAD device driver for Cisco NX-OS NXAPI

---
**NOTE**: This package is under active development and not distributed via pypi.  Code is not
considered alpha at this point.  You are welcome to look around and try things out, but
please be aware the code is subject to change without notice.
---

### NetCAD Configuration

Example `netcad.toml` file illustrates how to include this package into your
environment.

```toml
[[netcam.plugins]]

    name = "Cisco NX-OS"
    supports = ["nx-os"]

    # required, identifies the package containing the primary
    # NXAPI device-under-test definition.

    package = "netcam_aionxapi"

    # uses the provided design service check modules as part of this # plugin
    # package.

    services = [
        "netcam_aionxapi.topology",
        "netcam_aionxapi.bgp_peering",
    ]

    # use the following environment variables as the device login # credentials.

    config.env.username = "NETWORK_USERNAME"
    config.env.password = "NETWORK_PASSWORD"
```

Once installed, you will see the plugin listed in the `netcam` command:

```shell
$ netcam plugins list
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Name        ┃ Description                         ┃ Package         ┃ Supports  ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ Arista EOS  │ Arista EOS systems (asyncio)        │ netcam_aioeos   │ ['eos']   │
│ Cisco NX-OS │ Cisco NX-OS NXAPI systems (asyncio) │ netcam_aionxapi │ ['nx-os'] │
└─────────────┴─────────────────────────────────────┴─────────────────┴───────────┘
```
