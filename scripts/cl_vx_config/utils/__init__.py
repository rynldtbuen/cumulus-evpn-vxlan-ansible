import json
import os
import re
import yaml

import netaddr
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.errors import AnsibleError


class File:

    def __init__(self, fname=None):
        if fname is not None:
            self.fname = fname
            self.path = os.getcwd() + '/files/' + fname + '.json'

            with open(self.path, 'r') as f:
                self.data = json.load(f)

            self._data = self.data.copy()

    def dump(self):
        if self.data != self._data:
            with open(self.path, 'w') as f:
                json.dump(self.data, f)
            return self.data
        else:
            return self.data

    def master(self):
        path = os.getcwd() + '/master.yml'

        with open(path, 'r') as f:
            return yaml.load(f)

    @property
    def default(self):
        base_network = self.master['base_networks']
        default = {
            'clag_interfaces': {},
            'external_networks': {
                'base_network': base_network['external_connectivity'],
                'networks': {}
            },
            'vlans_network': {
                'base_network': base_network['vlans'],
                'networks': {}
            },
            'l3vni': {}
        }

        return default[self.fname]


class Interface:

    def __init__(self, interface):
        self.interface = interface

        try:
            base_name = (
                re.search(r'(\w+|\d+)(?<!\d)', self.interface).group(0)
            )
        except AttributeError:
            base_name = ''
        except TypeError:
            base_name = ''

        self.base_name = base_name

        id = str(self.interface).replace(self.base_name, '')

        if id.isdigit():
            self.id = int(id)
        if '-' in id:
            self.id = id
        if not id:
            raise AnsibleError('Invalid interface: ' + self.interface)

    def __repr__(self):
        return self.interface

    def __add__(self, num):
        if num == self.id:
            return self.interface
        else:
            return '{}-{}'.format(self.interface, self.id + num - 1)


class Network(netaddr.IPNetwork):

    def __init__(self, addr):
        super().__init__(addr)

        if self.network != self.ip:
            raise AnsibleError('Invalid network: ' + self.__str__())

    def __len__(self):
        return len(list(self.iter_hosts()))

    def __iter__(self):
        for item in self.iter_hosts():
            yield '{}/{}'.format(item, self.prefixlen)

    def get_subnet(self, existing_networks, prefixlen=24):
        # Get unique subnet base on existing networks
        available_networks = (
            netaddr.IPSet(self.cidr) - netaddr.IPSet(
                netaddr.cidr_merge([Network(net) for net in existing_networks])
            )
        )
        while len(available_networks.iter_cidrs()) > 0:
            for net in available_networks.iter_cidrs():
                for subnet in net.subnet(prefixlen, count=1):
                    existing_networks.append(str(subnet))
                    return str(subnet)
        else:
            raise AnsibleError('Run out of subnets')

    def get_ip(self, index, lo=False, addr=False):
        try:
            ip_addr = list(self.__iter__())[index - 1]
            if lo:
                return ip_addr.replace(str(self.prefixlen), '32')
            elif addr:
                return ip_addr.split('/')[0]
            else:
                return ip_addr
        except IndexError:
            err = True
        else:
            err = False

        if err:
            raise AnsibleError('Run out of IP addresses')

    def overlaps(self, other):
        return self.__contains__(other)

    @property
    def id(self):
        return re.search(r'^\d{2}', str(self.value)).group(0)

    @property
    def iprange(self):
        return netaddr.IPSet(self.cidr).iprange()


class MACAddr(netaddr.EUI):

    def __init__(self, addr):
        super().__init__(addr, dialect=netaddr.mac_unix_expanded)

    def __add__(self, index):
        return MACAddr(self.value + index).__str__()

    def __sub__(self, index):
        return MACAddr(self.value - index).__str__()


class Host:

    def __init__(self, host):
        self.host = host

        if self.host not in Inventory().hosts():
            raise AnsibleError('Host not found: ' + self.host)

        m = re.search(r'(?<=\w\d)\d+', self.host)
        self.id = int(m.group(0))

        if self.id % 2 == 0:
            rack_id = int(self.id - (self.id / 2))
        else:
            rack_id = int((self.id + 1) - (self.id + 1)/2)

        self.rack_id = rack_id

        self.rack = 'rack0' + str(self.rack_id)

    def __repr__(self):
        return self.host

    @property
    def peer_host(self):
        i = Inventory()
        for host in i.hosts():
            if host != 'localhost' and host != self.host:
                _host = Host(host)
                primary_group = i.groups(host, primary=True)
                if _host.rack_id == self.rack_id and (
                    primary_group == i.groups(self.host, primary=True)
                ):
                    return host


class Inventory:

    def __init__(self):
        self.inventory_source = os.getcwd() + '/devices'
        self.loader = DataLoader()

        self.inventory = InventoryManager(
            loader=self.loader, sources=[self.inventory_source]
        )

        # self.variable_manager = VariableManager(
        #     loader=self.loader, inventory=self.inventory
        #     )
        #
        # self.hostvars = HostVars(
        #     loader=self.loader,
        #     inventory=self.inventory,
        #     variable_manager=self.variable_manager
        #     )

    def __iter__(self):
        return iter([h for h in self.hosts() if h != 'localhost'])

    def _check_host(self, host):
        if host not in self.__iter__():
            raise AnsibleError(host + ' not found')

    def hosts(self, pattern='all'):
        try:
            return self.inventory.get_groups_dict()[pattern]
        except KeyError:
            self._check_host(pattern)
            return pattern

    def groups(self, host, primary=True):
        self._check_host(host)
        groups = []
        for k, v in self.inventory.get_groups_dict().items():
            if host in v and k != 'all':
                if primary:
                    return k
                else:
                    groups.append(k)
        return groups
