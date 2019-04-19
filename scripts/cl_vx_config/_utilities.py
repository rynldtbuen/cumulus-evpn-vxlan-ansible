from cl_vx_config.inventory import Inventory as inv
from ipaddress import IPv4Network, IPv4Address, AddressValueError
from netaddr import IPNetwork, IPSet, cidr_merge, EUI, mac_unix_expanded
from collections import defaultdict
from operator import itemgetter
from itertools import groupby, chain, permutations

import yaml
import json
import os
import re


class Utilities:

    def host_id(self, host):
        m = re.search(r'(?<=\w\d)\d+', host)
        return int(m.group(0))

    def rack_id(self, host, id=True):
        host_id = self.host_id(host)
        if host_id % 2 == 0:
            pair = host_id - 1
            x = host_id / 2
            rack_id = int(host_id - x)
        else:
            pair = host_id + 1
            x = pair / 2
            rack_id = int(pair - x)

        if id:
            return rack_id
        else:
            return 'rack0' + str(rack_id)

    def load_masterfile(self, variable):
        with open(os.getcwd() + '/master.yml', 'r') as f:
            return yaml.load(f)[variable]

    def load_basefile(self, variable):
        with open(os.getcwd() + '/base_config.yml', 'r') as f:
            return yaml.load(f)[variable]

    def load_datafile(self, file):
        with open(self._path_datafile(file), 'r') as f:
            return json.load(f)

    def _path_datafile(self, file):
        dir = os.getcwd() + "/files/"
        path = dir + file + '.json'
        return path

    def dump_datafile(self, file, data):
        filepath = self._path_datafile(file)
        with open(filepath, 'w') as f:
            json.dump(data, f)
        return data

    def get_ip(self, subnet, index, type=None, existing_ips=None):
        # uni_subnet = unicode(subnet)
        _subnet = IPv4Network(subnet, strict=False)

        try:
            if type == 'address':
                return str(_subnet[index])
            elif type == 'loopback':
                return str(_subnet[index]) + "/32"
            else:
                return str(_subnet[index]) + "/" + str(_subnet.prefixlen)
        except IndexError:
            return False

        # if existing_ips is not None:

    def r_get_ip(self, network, index, type='ipprefix'):
        net = IPNetwork(network)
        prefixlen = net.prefixlen
        hosts = list(net.iter_hosts())
        if type == 'ipprefix':
            return '{}/{}'.format(hosts[index], prefixlen)
        elif type == 'loopback':
            return '{}/32'.format(hosts[index])
        else:
            return str(hosts[index])

    def get_address(self, addr, index=None):
        try:
            address = IPv4Address(addr)
        except AddressValueError:
            address = IPv4Address(addr.split('/')[0])

        if index is None:
            return str(address)
        else:
            return str(address + index)

    def get_subnet(self, base_network, existing_networks, size_of_subnet=24):
        bn = IPSet(IPNetwork(base_network))
        en = IPSet(cidr_merge([IPNetwork(network)
                               for network in existing_networks]))
        available_networks = bn - en

        for network in available_networks.iter_cidrs():
            for subnet in network.subnet(size_of_subnet):
                existing_networks.append(str(subnet))
                yield str(subnet)

    def get_subnet_range(self, subnet):
        return IPSet(subnet).iprange()

    def interface(self, iface, type=None):
        m = re.search(r'(\w+|\d+)(?<!\d)', iface)
        base_name = m.group(0)

        if type is None:
            num = iface.replace(base_name, '')
            return int(num)
        else:
            return base_name

    def ifrange(self, iface, n):
        m = re.search(r'(\w+|\d+)(?<!\d)', iface)
        base_name = m.group(0)
        id = int(iface.replace(base_name, ''))
        range = id + n - 1
        return self.cluster_to_range('{}-{}'.format(iface, range))


    def mac_address(self, base_mac, index):
        _base_mac = EUI(base_mac)
        _index = int(index)
        if _index < 0:
            _mac_int = int(_base_mac) + (_index) + 1
        else:
            _mac_int = int(_base_mac) + (_index) - 1

        _mac_address = EUI(_mac_int, dialect=mac_unix_expanded)
        return str(_mac_address)

    def default_to_dict(self, d):
        if isinstance(d, defaultdict):
            d = {k: self.default_to_dict(v) for k, v in d.items()}
        return d

    def defaultset_to_list(self, d):
        if isinstance(d, defaultdict):
            d = {k: list(v) for k, v in d.items()}
        return d

    def map_attr(self, key, list_dict):
        if isinstance(list_dict, list):
            return list(map(itemgetter(key), list_dict))
        else:
            x = list(chain(*list_dict))
            return list(map(itemgetter(key), x))

    def flatten(self, list_dict):
        return list(chain(*list_dict))

    def difference(self, lista, listb):
        return list(set(lista) - set(listb))

    def unique(self, v):
        return list(set(v))

    def duplicate_items(self, v):
        return [item for item in set(v) if v.count(item) > 1]

    def range_to_cluster(self, v):
        if isinstance(v, list):
            value = v
        if isinstance(v, str):
            value = v.replace(' ', '').split(',')

        for item in value:
            try:
                m = re.match(r'(\w+|\d+)(?<!\d)', item)
                base_name = m.group(0)
            except AttributeError:
                base_name = ''

        try:
            range_format = [int(item.replace(base_name, '')) for item in v]
        except ValueError as error:
            return error

        groups = []
        for k, _v in groupby(enumerate(sorted(range_format)),
                             lambda x: x[1]-x[0]):
            groups.append(list(map(itemgetter(1), list(_v))))

        clustered = []
        for k in groups:
            if len(k) > 1:
                format = "{}{}-{}".format(base_name, k[0], k[-1])
            else:
                format = "{}{}".format(base_name, k[0])
            clustered.append(format)

        return ",".join(clustered)

    def cluster_to_range(self, v):
        try:
            value = [item.strip() for item in v.split(',')]
        except AttributeError:
            value = [_item for item in v for _item in item.split(',')]

        range_list = []
        for item in value:
            try:
                m = re.match(r'(\w+|\d+)(?<!\d)', item)
                base_name = m.group(0)
            except AttributeError:
                base_name = ''

            range_format = list(
                map(int, item.replace(base_name, '').split('-')))
            if len(range_format) > 1:
                for x in range(range_format[0], range_format[1] + 1):
                    range_list.append(base_name + str(x))
            else:
                range_list.append(base_name + str(range_format[0]))

        return range_list

    def range_cluster(self, v):
        return self.range_to_cluster(self.cluster_to_range(v))

    def get_links(self, link):
        # Return list of tuples of permutations of link base on Ansible Inventory
        # Argument format:'group/host:staring_port -- group/host:staring_port'
        # group and host must exist in ansible inventory
        # Ex. 'spine:swp1 -- leaf:swp21'
        # Return values: [(spine01, swp1, leaf01, swp21), leaf01, swp21, spine01, swp1]

        perm_links = list(permutations(
            [item.strip() for item in link.split('--')]))

        if slice:
            _links = perm_links[:len(perm_links)//2]
        else:
            _links = perm_links

        data = {'links': [], 'item': link, 'item_ifaces': {}}
        for index, _link in enumerate(_links):
            items = [x for item in _link for x in item.split(':')]
            dev_a, a_port, dev_b, b_port = items

            x = (
                sorted(inv.groups(dev_a)),
                self.ifrange(a_port, len(inv.groups(dev_b))),
                sorted(inv.groups(dev_b)),
                self.ifrange(b_port, len(inv.groups(dev_a)))
            )

            hosts, ifaces, nei, nei_ifaces = x

            for h in range(len(hosts)):
                for n in range(len(nei)):
                    data['links'].append(
                        (hosts[h], ifaces[n], nei[n], nei_ifaces[h]))

            if index == 0:
                data['item_ifaces'] = (
                    '{}:{} -- {}:{}'.format(dev_a, ifaces, dev_b, nei_ifaces)
                    )

        return data

    def links(self, links, slice=False):

        try:
            return self.get_links(links)
        except AttributeError:
            x = []
            for item in links:
                x.append(self.get_links(item))
            return x
