import json
import copy
import itertools

from cl_vx_config.utils import File, Inventory, MACAddr, Host, Network
from cl_vx_config.utils.checkconfig import CheckVars
from cl_vx_config.getconfig import GetConfig

cl = GetConfig()
device = Inventory()
checked = CheckVars()

configs = [
    # 'loopbacks',
    # '_vlans'
    # 'mlag_peerlink',
    # 'mlag_bonds',
    # '_host_vlans',
    # 'vxlan'
    '_vlans_network'
    # 'dummy'
]

for config in configs:
    method = getattr(cl, config)
    try:
        print(json.dumps(method(), indent=4))
    except json.decoder.JSONDecodeError:
        print(method())
    except TypeError:
        print(method())
