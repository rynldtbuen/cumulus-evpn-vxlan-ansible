import collections
import itertools
import re
import yaml


from ansible.errors import AnsibleError
# from itertools import combinations, permutations
# from ipaddress import IPv4Network
# from netaddr import IPNetwork
from cl_vx_config.utils.filters import Filters
from cl_vx_config.utils import File, Network

filter = Filters()
mf = File().master()


class CheckVars:

    def _yaml_f(self, data, style="", flow=None, start=True):
        return yaml.dump(
            data, default_style=style,
            explicit_start=start,
            default_flow_style=flow
        )

    @property
    def vlans(self):
        master_vlans = mf['vlans']

        vids = []
        for tenant, vlans in master_vlans.items():
            for vlan in vlans:
                vids.append(vlan['id'])

        dup_vids = [vid for vid in set(vids) if vids.count(vid) > 1]

        if len(dup_vids) > 0:
            error = {}
            for tenant, value in master_vlans.items():
                v = [v for v in value for d in dup_vids if v['id'] == d]
                if len(v) > 0:
                    error[tenant] = v
            msg = ("VLANID conflict:\nRefer to the errors "
                   "below and to your 'master.yml file\n{}")
            raise AnsibleError(
                msg.format(self._yaml_f({'vlans': error}))
            )

        return master_vlans

    @property
    def mlag_bonds(self):
        mlag_bonds = mf['mlag_bonds']

        vids = {}
        for tenant, vlans in self.vlans.items():
            ids = []
            for vlan in vlans:
                ids.append(vlan['id'])
                vids[tenant] = ids

        def _get_tenant(vid):
            return ''.join([
                k for k, v in self.vlans.items() for i in v if i['id'] == vid
            ])

        for rack, bonds in mlag_bonds.items():

            # Check for bonds member conflict
            mems = filter.cluster([v['members'] for v in bonds], _list=True)
            for mem in set(mems):
                if mems.count(mem) > 1:
                    self._mlag_bonds_error(
                        rack, mem, 'Bonds member conflict'
                    )

            # Check for bonds name conflict
            names = [v['name'] for v in bonds]
            for name in set(names):
                if names.count(name) > 1:
                    self._mlag_bonds_error(
                        rack, name, 'Bonds name conflict'
                    )

            for bond in bonds:
                set_items = set([])
                bond_vids = filter.cluster(bond['vids'], _list=True)

                for bond_vid in bond_vids:
                    # Check if assign vids exist in tenant vlans
                    if bond_vid not in [x for i in vids.values() for x in i]:
                        self._mlag_bonds_error(
                            rack, v['vids'], 'VLANIDs not found'
                        )

                if len(bond_vids) > 1:
                    for bond_vid in bond_vids:
                        set_items.add((_get_tenant(bond_vid), bond['vids']))

                if len(set_items) > 1:
                    title = 'Bonds assigned VLANID belongs to multiple tenant'
                    for item in set_items:
                        self._mlag_bonds_error(rack, item[1], title)

        return mlag_bonds

    def _mlag_bonds_error(self, rack, item, title):
        bonds = []
        for bond in mf['mlag_bonds'][rack]:
            if bond['members'] == item:
                bonds.append(bond)
            elif bond['name'] == item:
                bonds.append(bond)
            elif bond['vids'] == item:
                bonds.append(bond)

        if len(bonds) > 0:
            msg = ("{}:\nRefer to the errors below and "
                   "to your 'master.yml file.\n{}")

            raise AnsibleError(
                msg.format(title, self._yaml_f({'mlag_bonds': {rack: v}}))
            )

    @property
    def mlag_peerlink_interfaces(self):
        mlag_peerlink_interfaces = mf['mlag_peerlink_interfaces']
        ifaces = filter.cluster(mlag_peerlink_interfaces, _list=True)

        if len([i for i in set(ifaces) if ifaces.count(i) > 1]) > 0:
            msg = ("Interfaces conflict:\nRefer to the errors below and "
                   "to your 'master.yml file.\n{}")
            raise AnsibleError(
                msg.format(self._yaml_f({
                    'mlag_peerlink_interfaces': mlag_peerlink_interfaces
                }, flow=False)))

        return ','.join(ifaces)

    @property
    def base_networks(self):
        base_networks = mf['base_networks']

        def networks():
            networks = collections.defaultdict(list)
            for k, v in base_networks.items():
                if isinstance(v, dict):
                    for _k, _v in v.items():
                        net = Network(_v)
                        networks[net.id].append((k, _k, net))
                else:
                    net = Network(v)
                    networks[net.id].append((k, net))

            _networks = []
            for k, v in networks.items():
                _networks.extend(list(itertools.combinations(v, 2)))

            return _networks

        def overlaps():
            for items in networks():
                nets = items[0][-1], items[1][-1]
                net_a, net_b = sorted(nets)
                if net_a.overlaps(net_b):
                    return items

        if overlaps() is not None:
            error = collections.defaultdict(dict)
            for item in overlaps():
                if len(item) > 2:
                    error[item[0]][item[1]] = str(item[-1])
                else:
                    error[item[0]] = str(item[-1])
            msg = ("Networks conflict:\nRefer to the errors below and "
                   "to your 'master.yml file.\n{}")
            raise AnsibleError(
                msg.format(self._yaml_f(
                    {'base_networks': dict(error)}, flow=False))
            )

        return base_networks

    def vlans_network(self, tenant, vlan, vlans_network=None):
        vnp = Network(vlan['network_prefix'])

        # Check vlan subnet against base_networks
        for var, net in self.base_networks.items():
            if var != 'vlans':
                if var == 'loopbacks':
                    for group, network in net.items():
                        _net = Network(network)
                        if (vnp.overlaps(_net)
                                or _net.overlaps(vnp)):
                            msg = ("Networks conflict:\nRefer to the errors "
                                   "below and to your 'master.yml' file."
                                   "\n{}\n{}")
                            raise AnsibleError(msg.format(
                                self._yaml_f({'vlans': {tenant: [vlan]}}),
                                self._yaml_f({
                                    'base_networks': {var: {group: network}}},
                                    flow=False, start=False)
                            ))
                else:
                    _net = Network(net)
                    if (vnp.overlaps(_net)
                            or _net.overlaps(vnp)):
                        msg = ("Networks conflict:\nRefer to the errors "
                               "below and to your 'master.yml' file.\n{}\n{}")
                        raise AnsibleError(msg.format(
                            self._yaml_f({'vlans': {tenant: [vlan]}}),
                            self._yaml_f({
                                'base_networks': {var: net}},
                                flow=False, start=False)
                        ))

        # existing_networks = list(
        #     map(lambda x: x['subnet'], vlans_network.values())
        # )
        for k, v in vlans_network.items():
            _vnp = Network(v['network_prefix'])
            if (vnp.overlaps(_vnp)
                    or _vnp.overlaps(vnp)):
                msg = ("Networks conflict: {} overlaps with existing network "
                       "{}(VLAN{})\nRefer to the errors below and to your "
                       "'master.yml' file.\n{}")
                raise AnsibleError(msg.format(
                    str(vnp), str(_vnp), v['id'],
                    self._yaml_f({'vlans': {tenant: [vlan]}})
                ))
        # Check vlan subnet against existing vlans subnet

        # def _overlap_err(self, data):

        #     x = [_item for item in data for _item in item]
        #
        #     name = " and ".join([x[0], x[3]]) if x[0] != x[3] else x[0]
        #     _data = [x[idx] for idx, item in enumerate(x) if idx != 0 and idx != 3]
        #     _data.insert(0, name)
        #
        #     msg = ("Subnet {2}({1}) overlaps with subnet {4}({3})\n"
        #            "Check your '{0}' variable in 'master.yml'")
        #     raise AnsibleError(msg.format(*_data))
        #
        # def _cidr_check(self, v):
        #
        #     if str(IPNetwork(v[2]).cidr) != v[2]:
        #         msg = ("Invalid network: {2}({1})\n"
        #                "Check your '{0}' variable in 'master.yml'")
        #         raise AnsibleError(msg.format(*v))
        #     else:
        #         return v[0], v[1], IPv4Network(v[2])

        # def subnets(self, data=None):
        #
        #     base_networks = utils.load_masterfile('base_networks')
        #
        #     x = []
        #     for k, v in base_networks.items():
        #         if isinstance(v, dict):
        #             for _k, _v in v.items():
        #                 x.append(
        #                     ('base_networks', '{}({})'.format(k, _k), _v)
        #                     )
        #         else:
        #             x.append(('base_networks', k, v))
        #
        #     y = []
        #     for item in x:
        #         checked = self._cidr_check(item)
        #         y.append(checked)
        #
        #     if data is None:
        #         for item in combinations(y, 2):
        #             if item[0][2].overlaps(item[1][2]):
        #                 self._overlap_err(item)
        #     else:
        #         for item in y:
        #             if item[2].overlaps(data[2]):
        #                 self._overlap_err([item, data])
        #
        # def _variable_items(self, data):
        #     links = ['external_connectivity', 'fabric']
        #     host, iface, vars = data
        #
        #     err_items = []
        #     for var in vars:
        #         if var in links:
        #             t = []
        #             for link in utils.load_masterfile(var):
        #                 x = [x for item in link.split('--')
        #                      for x in item.strip().split(':')]
        #                 dev_a, a_port, dev_b, b_port = x
        #
        #                 data = (
        #                     sorted(inv.groups(dev_a)),
        #                     utils.ifrange(a_port, len(inv.groups(dev_b))),
        #                     sorted(inv.groups(dev_b)),
        #                     utils.ifrange(b_port, len(inv.groups(dev_a)))
        #                     )
        #                 hosts, ports, nei, nei_ports = data
        #                 t.append((dev_a, ports, dev_b, nei_ports))
        #
        #             _links = []
        #             for index, item in enumerate(t):
        #                 group_a, ifaces_a, group_b, ifaces_b = item
        #                 for g in [group_a, group_b]:
        #                     if host in inv.groups(g) and (iface in ifaces_a or iface in ifaces_b):
        #                         group = g
        #                         _links.append('{0}:{1} -- {2}:{3}'.format(*item))
        #
        #                         err_items.append([yaml.dump({var: _links}, default_flow_style=False, indent=4), group, var, iface])
        #
        #         if var == 'mlag_bonds':
        #             for rack, value in utils.load_masterfile(var).items():
        #                 if utils.rack_id(host, id=False) == rack:
        #                     for item in value:
        #                         if iface == item['members']:
        #                             err_items.append([yaml.dump(
        #                                 {var: {rack: [item]}}, default_style=""), rack, var, iface])
        #
        #     return self._overlapping_ifaces_err(err_items)
        #
        # def _overlapping_ifaces_err(self, data):
        #
        #     x = [i for item in data for i in item]
        #
        #     if len(x) > 4:
        #         items = "\n".join([x[0], x[4]])
        #         vars = " and ".join([x[2], x[6]])
        #         name = '{1}({2}), {5}({6})'.format(*x)
        #         iface = x[3]
        #     else:
        #         items, name, vars, iface = x
        #
        #     msg = ("Overlapping interface: {} in {}\nCheck the error "
        #            "below and the variable in master.yml file\n---\n{}")
        #     raise AnsibleError(msg.format(iface, name, items))
        #
        # def interfaces(self, interfaces):
        #     x = []
        #     for host in interfaces:
        #         ifaces = [i for a in interfaces[host].values() for i in a]
        #
        #         for item in combinations(ifaces, 2):
        #             if item[0] == item[1]:
        #                 x.append([host, item[0]])
        #
        #     try:
        #         host, iface = x[0]
        #         vars = []
        #         for var, ifaces in interfaces[host].items():
        #             if iface in ifaces:
        #                 vars.append(var)
        #         x[0].append(vars)
        #         return self._variable_items(x[0])
        #     except IndexError:
        #         pass
        # if len(x) > 0:
        #
        # return x
        # for var, ifaces in interfaces[host].items():
        # if var in var_links:
        #     combine_ifaces = combinations(ifaces, 2)
        #     for item in combine_ifaces:
        #         if item[0] == item[1]:
        #             self._overlapping_ifaces_err((var, host, item[0]))

        # var_combine = list(combinations(interfaces[host].keys(), 2))
        # if len(var_combine) > 0:
        #     _interfaces = interfaces[host]
        #     for item in var_combine:
        #         var_a, var_b = item
        #         for iface in _interfaces[var_a]:
        #             if iface in _interfaces[var_b]:
        #                 data = [(var_a, host, iface), (var_b, host, iface)]
        # return self._overlapping_ifaces_err(data)

        # x = {var: self._links(var, host, item[0])}
        # msg = ("Overlapping interfaces:\n"
        #        "Check the error below and '{}' "
        #        "variable in 'master.yml'\n---\n{}")
        # raise AnsibleError(
        #     msg.format(var, yaml.dump(
        #         x, default_flow_style=False)
        #     )
        # )
        # combine_var = combinations
        #         # y = combinations(v.keys(), 2)
        #         # for a, b in y:
        #         #     for intf in v[a]:
        #         #         if intf in v[b]:
        #         #             msg = ("Overlapping interface: {} in {}\n"
        #         #                    "Check your '{}' and '{}' variable in 'master.yml'")
        #         #             raise AnsibleError(msg.format(intf, host, a, b))

        # # def _reserved_subnets(self, data):
        # #     reserved_subnets = {
        # #         '172.16.0.0/14': 'VLANs',
        # #         '172.20.0.0/24': 'External Connectivity'
        # #         }
        # #
        # #     var, name, subnet = data
        # #     _data_list = list(data)
        # #     for rsv_subnet, name in reserved_subnets.items():
        # #         if subnet.overlaps(IPv4Network(rsv_subnet)):
        # #             _data_list.extend([name, rsv_subnet])
        # #             msg = ("Subnet {2}({1}) overlaps with reserved subnet {4}({3})\n"
        # #                    "Check your '{0}' variable in 'master.yml'")
        # #             raise AnsibleError(msg.format(*_data_list))
        #
        # # def vlans_subnet(self, data=None, existing_vlans=None):
        # #
        # #     _data = self._cidr_check(data)
        # #     name, id, subnet = _data
        # #     _data_list = list(data)
        # #
        # #     for k, v in existing_vlans.items():
        # #         if IPv4Network(subnet).overlaps(IPv4Network(v['subnet'])):
        # #             _data_list.extend([k, v['subnet']])
        # #             msg = ("VLAN{1}({2}) subnet overlaps with existing subnet of VLAN{3}({4})\n"
        # #                    "Check your '{0}' variable in 'master.yml'")
        # #             raise AnsibleError(msg.format(*_data_list))
        # #
        # #     self._reserved_subnets(_data)
        # #
        # #     self.loopbacks_subnet(_data)
        #
        # # def links(self, links):
        # #     for name, group in links.items():
        # #         for _group, value in group.items():
        # #             try:
        # #                 iface = [y for x in self.utils.map_attr(
        # #                     'iface_range', value) for y in x]
        # #             except KeyError:
        # #                 iface = [x for x in self.utils.map_attr(
        # #                     'iface', value)]
        # #             dup_iface = self.utils.duplicate_items(iface)
        # #             if len(dup_iface) > 0:
        # #                 try:
        # #                     in_item = [
        # #                         item['in_item']
        # #                         for item in value if dup_iface[0] == item['iface']]
        # #                 except KeyError:
        # #                     in_item = (
        # #                         [item['in_item'] for item in value
        # #                             if dup_iface[0] in item['iface_range']]
        # #                         )
        # #                 msg = ("Overlapping interface: {} in {}\n"
        # #                        "Check your 'master.yml' and the errors below\n{}")
        # #                 raise AnsibleError(msg.format(
        # #                     dup_iface[0],
        # #                     _group, json.dumps({name: in_item}, indent=2))
        # #                     )
