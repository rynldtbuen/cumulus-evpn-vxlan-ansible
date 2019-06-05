import json
import re
# from cl_vx_config.configvars import ConfigVars
# from cl_vx_config.utils.checkvars import CheckVars
# from cl_vx_config.utils.filters import Filters
from cl_vx_config.utils import Host

# cl = ConfigVars()
# checkvars = CheckVars()
# filter = Filters()

configs = [
    # '_vlans'
    # '_host_vlans'
    # 'loopback_ips',
    # 'mlag_peerlink',
    # 'mlag_bonds',
    # 'vxlans',
    # 'vlans_interface',
    # 'ip_interfaces',
    # 'unnumbered_interfaces',
    # 'bgp_neighbors',
    'l3vni'
]

x = int(re.split('(\\d+)', 'dc2_leaf01')[-2])

print(x)
# for config in configs:
#     method = getattr(cl, config)
#     try:
#         print(json.dumps(method(), indent=4))
#     except json.decoder.JSONDecodeError:
#         print(method())
#     except TypeError:
#         print(method())

# print(cl._host_vlans)
