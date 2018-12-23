from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager
from ansible.vars.manager import VariableManager
from ansible.vars.hostvars import HostVars
from core import GetConfigVars
from jinja2 import Environment, FileSystemLoader
import json
import re
import subprocess
import os

# fabric = [
#   'spine:swp1 -- leaf:swp21',
#   'spine:swp23 -- border:swp23',
#   'spine:swp10 -- leaf:swp10'
#   ]
#
# fabric1 = [
#   'edge01:eth2 -- border01:swp1',
#   'edge01:eth3 -- border02:swp1'
#   ]
# x = ['leaf01', 'leaf02', 'leaf03', 'leaf04', 'leaf05', 'leaf06', ]
getconfigvars = GetConfigVars()
print(json.dumps(getconfigvars._hostvars('mgmt_hwaddr'), indent=4))
# print(getconfigvars.dnsmasq())
# inventory_filename = os.getcwd() + '/devices'
# data_loader = DataLoader()
# inventory = InventoryManager(loader=data_loader,
#                        sources=[inventory_filename])
#
# variable_manager = VariableManager(loader=data_loader, inventory=inventory)
#
#
# hosts = inventory.get_groups_dict()['cumulus']
#
# # for host in x:
# #     y = Host(host)
# #     print(y.get_groups())
#
# # y = variable_manager.get_vars()
#
# x =
#
# for host in hosts:
#     y = x.raw_get(host)['mgmt_hwaddr']
#     print(host, y)
