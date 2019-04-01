from cl_vx_config.getconfigvars import GetConfigVars
from cl_vx_config.gns3 import GNS3Project, GNS3Node
from cl_vx_config.utilities import Utilities
from cl_vx_config.checkconfigvars import CheckConfigVars

import json


utils = Utilities()
checkconfigvars = CheckConfigVars()
getconfigvars = GetConfigVars()

# x = getconfigvars.revised_link('spine:swp1 -- leaf:swp21')

# configs = [
#     # 'vxlan',
#     # 'svi',
#     # 'interfaces_ip',
#     # 'bgp',
#     # 'loopback',
#     # 'interfaces_unnumbered',
#     # 'interfaces_list',
#     # '_vlans_subnet',
#     # 'external_connectivity',
#     # 'fabric',
#     # 'mlag',
#     'revised_link'
# ]

base_url = "http://10.0.0.254:3080/v2"
node = GNS3Node(base_url, 'test01', 'spine01', 'qemu')
print(json.dumps(list(node._get_appliances), indent=4))
