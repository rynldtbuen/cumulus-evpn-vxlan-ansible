from ipaddress import IPv4Network, AddressValueError
from core import GetConfigVars
from helpers import Utilities, CheckVars
import json
from itertools import combinations
configs = [
   'mlag',
   # 'vxlan',
   # 'svi',
   # 'interfaces_ip',
   # 'bgp',
   # 'loopback',
   # 'interfaces_unnumbered',
   # 'interfaces_ip',
   # 'interfaces_list',
   # '_vlans_subnet'
    ]

getconfigvars = GetConfigVars()

for config in configs:
    x = getattr(getconfigvars, config)
    try:
        print(config)
        print(json.dumps(x(), indent=4))
    except TypeError:
        print(x())

# x = {'vlans': ['172.24.0.0/24']}
#
# for name, v in x.items():
#     print(v[0])
