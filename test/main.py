from cl_vx_config.core import GetConfigVars

import json

getconfigvars = GetConfigVars()


# print(x.mlag())
configs = [
    # 'vxlan',
    # 'svi',
    # 'interfaces_ip',
    # 'bgp',
    # 'loopback',
    # 'interfaces_unnumbered',
    'interfaces_list',
    # '_vlans_subnet',
    # 'external_connectivity',
    # 'fabric',
    # 'mlag'
]

print(getconfigvars.interfaces_list())
for config in configs:
    x = getattr(getconfigvars, config)
    try:
        # print(config)
        print(json.dumps(x(), indent=4))
    except TypeError:
        print(x())
