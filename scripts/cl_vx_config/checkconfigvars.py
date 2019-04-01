from cl_vx_config.utilities import Utilities
from ansible.errors import AnsibleError
from itertools import combinations
from ipaddress import IPv4Network
from netaddr import IPNetwork

import json


class CheckConfigVars:

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
                tenant, vid = (
                    self._get_tenant(
                        duplicate_vids[0], existing_vlans)
                        )
                msg = (
                    "VLAN{} is already assign to tenant '{}', "
                    "or has a duplicate entry. Plese check "
                    "your 'vlans' variable in 'master.yml'"
                    )
                raise AnsibleError(msg.format(vid, tenant))
            except TypeError:
                msg = "VLAN{} is found duplicate."
                raise AnsibleError(msg.format(duplicate_vids[0]))

    def mlag_bonds(self, vlans, mlag_bonds):

        for rack, value in mlag_bonds.items():

            vids = self.utils.unique(
                self.utils.cluster_to_range([item['vids'] for item in value]))
            for vid in vids:
                if vid not in vlans.keys():
                    m = ("VLAN{}({}) does not exist in list of VLANS. "
                         "Check your 'mlag_bonds' variable in 'master.yml'.")
                    raise AnsibleError(m.format(vid, rack))

            for bond in value:
                vids = self.utils.unique(
                    self.utils.cluster_to_range(bond['vids']))
                bond_tenant = self.utils.unique(
                    [vlans[vid]['tenant'] for vid in vids])
                if len(bond_tenant) > 1:
                    m = (
                        "Bond '{}' assigned vids belongs to multiple tenants. "
                        "Check your 'mlag_bonds' variable in 'master.yml'."
                        )
                    raise AnsibleError(
                        m.format(bond['name'])
                        )

            bond_members = (
                self.utils.cluster_to_range(
                    [item['members'] for item in value])
                    )
            dup_member = self.utils.duplicate_items(bond_members)
            if len(dup_member) > 0:
                m = (
                    "Port '{}'({}) is already assigned or "
                    "has a duplicate entry. Check your "
                    "'mlag_bonds' variable in 'master.yml'."
                    )
                raise AnsibleError(m.format(dup_member[0], rack))

            bonds = [item['name'] for item in value]
            dup_bonds = self.utils.duplicate_items(bonds)
            if len(dup_bonds) > 0:
                m = (
                    "Bond '{}'({}) was already assigned or "
                    "has a duplicate entry. Check your "
                    "'mlag_bonds' variable in 'master.yml'."
                    )
                raise AnsibleError(m.format(dup_bonds[0], rack))

    def _overlap_err(self, data):

        x = [_item for item in data for _item in item]

        name = " and ".join([x[0], x[3]]) if x[0] != x[3] else x[0]
        _data = [x[idx] for idx, item in enumerate(x) if idx != 0 and idx != 3]
        _data.insert(0, name)

        msg = ("Subnet {2}({1}) overlaps with subnet {4}({3})\n"
               "Check your '{0}' variable in 'master.yml'")
        raise AnsibleError(msg.format(*_data))

    def _reserved_subnets(self, data):
        reserved_subnets = {
            '172.16.0.0/14': 'VLANs',
            '172.20.0.0/24': 'External Connectivity'
            }

        var, name, subnet = data
        _data_list = list(data)
        for rsv_subnet, name in reserved_subnets.items():
            if subnet.overlaps(IPv4Network(rsv_subnet)):
                _data_list.extend([name, rsv_subnet])
                msg = ("Subnet {2}({1}) overlaps with reserved subnet {4}({3})\n"
                       "Check your '{0}' variable in 'master.yml'")
                raise AnsibleError(msg.format(*_data_list))

    def _cidr_check(self, v):

        if str(IPNetwork(v[2]).cidr) != v[2]:
            msg = ("Invalid network: {2}({1})\n"
                   "Check your '{0}' variable in 'master.yml'")
            raise AnsibleError(msg.format(*v))
        else:
            return v[0], v[1], IPv4Network(v[2])

    def loopbacks_subnet(self, data=None):

        loopbacks_subnet = {
            'loopback_ipv4_base_subnet': self.utils.load_masterfile(
                'loopback_ipv4_base_subnet'),
            'mlag_vxlan_anycast_base_subnet': {
                'clag_anycast': self.utils.load_masterfile(
                    'mlag_vxlan_anycast_base_subnet')}
            }

        loopbacks_t = []
        for k, v in loopbacks_subnet.items():
            for _name, _subnet in v.items():
                t = self._cidr_check((k, _name, _subnet))
                self._reserved_subnets(t)
                loopbacks_t.append(t)

        if data is None:
            for item in combinations(loopbacks_t, 2):
                if item[0][2].overlaps(item[1][2]):
                    self._overlap_err(item)

        else:
            for item in loopbacks_t:
                if item[2].overlaps(data[2]):
                    self._overlap_err([item, data])

    def vlans_subnet(self, data=None, existing_vlans=None):

        _data = self._cidr_check(data)
        name, id, subnet = _data
        _data_list = list(data)

        for k, v in existing_vlans.items():
            if IPv4Network(subnet).overlaps(IPv4Network(v['subnet'])):
                _data_list.extend([k, v['subnet']])
                msg = ("VLAN{1}({2}) subnet overlaps with existing subnet of VLAN{3}({4})\n"
                       "Check your '{0}' variable in 'master.yml'")
                raise AnsibleError(msg.format(*_data_list))

        self._reserved_subnets(_data)

        self.loopbacks_subnet(_data)

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
                        in_item = (
                            [item['in_item'] for item in value
                                if dup_iface[0] in item['iface_range']]
                            )
                    msg = ("Overlapping interface: {} in {}\n"
                           "Check your 'master.yml' and the errors below\n{}")
                    raise AnsibleError(msg.format(
                        dup_iface[0],
                        _group, json.dumps({name: in_item}, indent=2))
                        )

    def interfaces_list(self, interfaces_list):
        for host, v in interfaces_list.items():
            y = combinations(v.keys(), 2)
            for a, b in y:
                for intf in v[a]:
                    if intf in v[b]:
                        msg = ("Overlapping interface: {} in {}\n"
                               "Check your '{}' and '{}' variable in 'master.yml'")
                        raise AnsibleError(msg.format(intf, host, a, b))
