from ipaddress import IPv4Network, IPv4Address, AddressValueError
from netaddr import IPNetwork, IPSet, cidr_merge, EUI, mac_unix_expanded
from collections import defaultdict
from operator import itemgetter
from itertools import groupby, chain, combinations

import yaml
import json
import os
import re


class Utilities:

    def load_masterfile(self, variable):
        with open(os.getcwd() + '/master.yml', 'r') as f:
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
        _subnet = IPv4Network(subnet)

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

    def interface(self, iface, type=None):
        m = re.search(r'(\w+|\d+)(?<!\d)', iface)
        base_name = m.group(0)

        if type is None:
            num = iface.replace(base_name, '')
            return int(num)
        else:
            return base_name

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


class CheckVars:

    def __init__(self):
        self.utils = Utilities()

    def _get_tenant(self, vid, data):
        for k, v in data.items():
            _vid = vid == k
            if _vid:
                return v['tenant'], k

    def vlans(self, existing_vlans, vlans):
        vids = [item['id'] for item in vlans]

        duplicate_vids = self.utils.duplicate_items(vids)
        if len(duplicate_vids) > 0:
            try:
                tenant, vid = self._get_tenant(duplicate_vids[0],
                                               existing_vlans)
                m = ("VLAN{} is already assign to tenant \"{}\", "
                     "or has a duplicate entry. Plese check "
                     "your 'vlans' variable in 'master.yml'")
                raise Exception(m.format(vid, tenant))
            except TypeError:
                m = "VLAN{} is found duplicate."
                raise Exception(m.format(duplicate_vids[0]))

    def mlag_bonds(self, vlans, mlag_bonds):

        for rack, value in mlag_bonds.items():

            vids = self.utils.unique(
                self.utils.cluster_to_range([item['vids'] for item in value]))
            for vid in vids:
                if vid not in vlans.keys():
                    m = ("VLAN{}({}) does not exist in list of VLANS. "
                         "Check your 'mlag_bonds' variable in 'master.yml'.")
                    raise Exception(m.format(vid, rack))

            for bond in value:
                vids = self.utils.unique(
                    self.utils.cluster_to_range(bond['vids']))
                bond_tenant = self.utils.unique(
                    [vlans[vid]['tenant'] for vid in vids])
                if len(bond_tenant) > 1:
                    m = ("Bond '{}' assigned vids belongs to multiple tenants. "
                         "Check your 'mlag_bonds' variable in 'master.yml'.")
                    raise Exception(
                        m.format(bond['name']))

            bond_members = self.utils.cluster_to_range(
                [item['members'] for item in value])
            dup_member = self.utils.duplicate_items(bond_members)
            if len(dup_member) > 0:
                m = ("Port '{}'({}) is already assigned or has a duplicate entry. "
                     "Check your 'mlag_bonds' variable in 'master.yml'.")
                raise Exception(m.format(dup_member[0], rack))

            bonds = [item['name'] for item in value]
            dup_bonds = self.utils.duplicate_items(bonds)
            if len(dup_bonds) > 0:
                m = ("Bond '{}'({}) was already assigned or has a duplicate entry. "
                     "Check your 'mlag_bonds' variable in 'master.yml'.")
                raise Exception(m.format(dup_bonds[0], rack))

    def reserved_subnets(self, subnets):
        reserved_subnets = {'172.16.0.0/14': 'VLANs',
                            '172.20.0.0/24': 'External Connectivity'}

        # _subnets = [IPv4Network(subnet) for name, subnet in subnets]
        r_subnets = [IPv4Network(item) for item in reserved_subnets.keys()]
        for name, subnet in subnets.items():
            for _subnet in subnet:
                subnet_ = IPv4Network(_subnet)
                for r_subnet in r_subnets:
                    if subnet_.overlaps(r_subnet):
                        m = ("Subnet {} overlaps with {} "
                             "reserved subnet {}.\n"
                             "Check your '{}' variable in 'master.yml'.")
                        raise Exception(m.format(
                            subnet_, reserved_subnets[str(r_subnet)],
                            r_subnet, name))

    def subnets(self, new_subnets, existing_subnets=None, vlans=None):

        def _get_tenant_vid(subnet):
            for k, v in existing_subnets.items():
                if v['subnet'] == subnet:
                    return vlans[k]['tenant'], k

        invalid_subnets = []
        _new_subnets = []
        try:
            for name, v in new_subnets.items():
                for ns in v:
                    _new_subnets.append(IPv4Network(ns))
        except ValueError:
            invalid_subnets.append(ns)

        if len(invalid_subnets) > 0:
            m = ("Invalid network: {}, is an "
                 "IP address that belong to {} network.\n"
                 "Check your '{}' variable in 'master.yml'")
            raise ValueError(m.format(
                    ns, IPv4Network(ns, strict=False), name)
            )

        # if existing_subnets is not None:
        #     _existing_subnets = [IPv4Network(es['subnet'])
        #                          for _, es in existing_subnets.items()]
        #     if _new_subnets[0] in _existing_subnets:
        #         tenant, vlan = _get_tenant_vid(new_subnets)
        #         m = "Subnet {} is alreay assigned to VLAN{}({})."
        #         raise Exception(m.format(_new_subnets, vlan, tenant))
        #
        #     for es in _existing_subnets:
        #         if _new_subnets[0].overlaps(es):
        #             tenant, vlan = _get_tenant_vid(str(es))
        #             m = ("Subnet {} overlaps with existing subnet {}(VLAN{}).")
        #             raise Exception(m.format(_new_subnets[0], es, vlan))
        # else:
        #     x_subnets = combinations(_new_subnets, 2)
        #     for subnet in x_subnets:
        #         a, b = subnet
        #         if a.overlaps(b):
        #             m = "Overlapping subnets: ({}, {})."
        #             raise Exception(
        #                 m.format(str(a), str(b))
        #             )

            #    if _new_subnets in _existing_subnets:
            #         tenant, vlan = _get_tenant_vid(new_subnets)
            #         m = "Subnet {} is alreay assigned to VLAN{}({})."
            #         raise Exception(m.format(_new_subnets, vlan, tenant))
            #
            #     for item in _existing_subnets:
            #         if _new_subnets.overlaps(item):
            #             tenant, vlan = _get_tenant_vid(str(item))
            #             m = ("Subnet {} overlaps with existing subnet {}(VLAN{}).")
            #             raise Exception(m.format(_new_subnets, item, vlan))
            # except ValueError:
            #     m = ("Invalid network: {}, it is an "
            #          "IP address that belong to {} network.")
            #     raise Exception(m.format(
            #             new_subnets, IPv4Network(new_subnets, strict=False))
            #     )
        # if isinstance(new_subnets, str):
        #     try:
        #         _existing_subnets = [
        #             IPv4Network(es['subnet'])
        #             for _, es in existing_subnets.items()]
        #         _new_subnets = IPv4Network(new_subnets)
        #
        #         if _new_subnets in _existing_subnets:
        #             tenant, vlan = _get_tenant_vid(new_subnets)
        #             m = "Subnet {} is alreay assigned to VLAN{}({})."
        #             raise Exception(m.format(_new_subnets, vlan, tenant))
        #
        #         for item in _existing_subnets:
        #             if _new_subnets.overlaps(item):
        #                 tenant, vlan = _get_tenant_vid(str(item))
        #                 m = ("Subnet {} overlaps with existing subnet {}(VLAN{}).")
        #                 raise Exception(m.format(_new_subnets, item, vlan))
        #     except ValueError:
        #         m = ("Invalid network: {}, it is an "
        #              "IP address that belong to {} network.")
        #         raise Exception(m.format(
        #                 new_subnets, IPv4Network(new_subnets, strict=False))
        #         )
        # else:
        #     try:
        #         _new_subnets = []
        #         for item in new_subnets:
        #             _new_subnets.append(IPv4Network(item))
        #
        #         x_subnets = combinations(_new_subnets, 2)
        #         for subnet in x_subnets:
        #             a, b = subnet
        #             if a.overlaps(b):
        #                 m = "Overlapping subnets: ({}, {})."
        #                 raise Exception(
        #                     m.format(str(a), str(b))
        #                 )
        #     except ValueError:
        #         m = ("Invalid network: {}, it is an "
        #              "IP address that belong to {} network.")
        #         raise Exception(
        #             m.format(item, IPv4Network(item, strict=False))
        #         )
        # for es in _existing_subnets:
        #     if _new_subnets in
        # _new_subnets = []
        # for subnet in new_subnets:
        #     try:
        #         _new_subnets.append(IPv4Network(subnet))
        #     except ValueError:
        #         m = ("Invalid network: {}{}, it is an "
        #              "IP address that belong to {} network.")
        #         raise Exception(
        #             m.format(
        #                 subnet, _get_vid(subnet, 'vlans'), IPv4Network(
        #                     subnet, strict=False)))
        #
        # x_subnets = combinations(_new_subnets, 2)
        # for subnet in x_subnets:
        #     if subnet[0] == subnet[1]:
        #         m = ("Duplicate subnet: {}. "
        #              "Check your 'vlans' variable in 'master.yml'")
        #         raise Exception(m.format(subnet[0]))
        #
        #     if subnet[0].overlaps(subnet[1]):
        #         m = ("Subnets {}{} overlaps with subnet {}{}. "
        #              "Check your 'vlans' variable in 'master.yml'")
        #         value0 = _get_vid(str(subnet[0]), 'vlans')
        #         value1 = _get_vid(str(subnet[1]), 'vlans')
        #         raise Exception(
        #             m.format(subnet[0], value0,
        #                      subnet[1], value1))
        #
        # _existing_subnets = [IPv4Network(es['subnet'])
        #                      for _, es in existing_subnets.items()]
        # y_subnets = [(ns, es)
        #              for ns in _new_subnets for es in _existing_subnets]
        # for subnet in y_subnets:
        #     if subnet[0] == subnet[1]:
        #         m = "Subnet {}{} was already assigned to {}"
        #         value0 = _get_vid(str(subnet[0]), 'vlans')
        #         value1 = _get_vid(str(subnet[1]), 'existing_subnets')
        #         raise Exception(m.format(subnet[0], value0, value1))

        # if subnet[0].overlaps(subnet[1]):
        #     m = ("Subnet {}{} overlaps with existing subnet {}{}. "
        #          "Check your 'vlans' variable in 'master.yml'")
        #     value0 = _get_vid(str(subnet[0]), 'vlans')
        #     value1 = _get_vid(str(subnet[1]), 'existing_subnets')
        #     raise Exception(m.format(subnet[0], value0,
        #                              subnet[1], value1))

    def links(self, links):
        for name, group in links.items():
            for _group, value in group.items():
                try:
                    iface = [y for x in self.utils.map_attr(
                        'iface_range', value) for y in x]
                except KeyError:
                    iface = [x for x in self.utils.map_attr(
                        'iface', value)]
                dup_iface = self.utils.duplicate_items(iface)
                if len(dup_iface) > 0:
                    try:
                        in_item = [
                            item['in_item']
                            for item in value if dup_iface[0] == item['iface']]
                    except KeyError:
                        in_item = [
                            item['in_item']
                            for item in value if dup_iface[0] in item['iface_range']]

                    m = ("Overlapping interface: '{}' "
                         "in '{}'. Check your 'master.yml' "
                         "and the errors below.\n{}")
                    raise ValueError(m.format(
                        dup_iface[0], _group, json.dumps(
                            {name: in_item}, indent=2)
                        ))

    def interfaces_list(self, interfaces_list):
        for host, v in interfaces_list.items():
            y = combinations(v.keys(), 2)
            for a, b in y:
                for intf in v[a]:
                    if intf in v[b]:
                        m = ("Overlapping interface: {} in {}. "
                             "Check your \"{}\" and \"{}\" variable in \"master.yml\".")
                        raise Exception(m.format(intf, host, a, b))
