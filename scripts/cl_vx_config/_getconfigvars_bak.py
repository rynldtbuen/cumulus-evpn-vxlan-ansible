from cl_vx_config.utilities import Utilities
from cl_vx_config.checkconfigvars import CheckConfigVars

from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.vars.hostvars import HostVars
from ansible.errors import AnsibleError
from jinja2 import Environment, FileSystemLoader
from operator import itemgetter
from collections import defaultdict
from itertools import permutations

import os
import re


class GetConfigVars:

    def __init__(self):
        self.inventory_source = os.getcwd() + '/devices'
        self.loader = DataLoader()
        self.inventory = InventoryManager(
            loader=self.loader, sources=[self.inventory_source]
            )

        self.variable_manager = VariableManager(
            loader=self.loader, inventory=self.inventory
            )

        self.hostvars = HostVars(
            loader=self.loader,
            inventory=self.inventory,
            variable_manager=self.variable_manager
            )

        self.utils = Utilities()
        self.check = CheckConfigVars()

    def _groups(self, name=None):
        groups = self.inventory.get_groups_dict()
        if name is None:
            return groups['network_device']
        else:
            try:
                return groups[name]
            except KeyError:
                pass

        if name not in groups['all']:
            raise AnsibleError(name + ' not found')
        else:
            return [name]
        if name not in self._group_names():
            raise AnsibleError(name + ' not found')

    def _group_names(self, host=None):
        groups = self.inventory.get_groups_dict()
        group_names = []
        if host is None:
            return list(groups.keys())
        else:
            for k, v in groups.items():
                if host in v and k != 'all':
                    group_names.append(k)
            return group_names

    def _hostvars(self, name, groups='network_device'):
        vars = {}
        groups = self._groups(groups)
        hostvars = self.hostvars
        for host in groups:
            try:
                vars[host] = hostvars.raw_get(host)[name]
            except KeyError:
                vars[host] = None

        return vars

    def _host_id(self, host):
        m = re.search(r'(?<=\w\d)\d+', host)
        return int(m.group(0))

    def _rack_id(self, host, type=None):
        host_id = self._host_id(host)
        if host_id % 2 == 0:
            pair = host_id - 1
            x = host_id / 2
            rack_id = int(host_id - x)
        else:
            pair = host_id + 1
            x = pair / 2
            rack_id = int(pair - x)

        if type is None:
            return rack_id
        else:
            return 'rack0' + str(rack_id)

    # def _loopback_ipv4_address(self, host):
    #     base_subnet = self.utils.load_masterfile(
    #         'loopback_ipv4_base_subnet')
    #
    #     for group, subnet in base_subnet.items():
    #         if host in self._groups(group):
    #             host_id = self._host_id(host)
    #             return self.utils.get_ip(
    #                 subnet, host_id, 'loopback'
    #             )

    def loopbacks(self):

        self.check.subnets()

        base_subnet = (
            self.utils.load_masterfile('base_subnets')['loopbacks']
            )
        clag_vxlan_anycast_base_subnet = (
            self.utils.load_masterfile('base_subnets')['vxlan_anycast']
            )

        _loopback = {}
        for group, subnet in base_subnet.items():
            for host in self._groups(group):
                _loopback[host] = {
                    'ip_addresses': [], 'clag_vxlan_anycast_ip': None
                    }

                rack_id = self._rack_id(host)
                host_id = self._host_id(host)
                lo_ip = self.utils.get_ip(subnet, host_id, 'loopback')

                _loopback[host]['ip_addresses'].append(lo_ip)

                if host in self._groups('leaf'):
                    vxlan_anycast_ip = self.utils.get_ip(
                        clag_vxlan_anycast_base_subnet, rack_id, 'address')

                    _loopback[host]['clag_vxlan_anycast_ip'] = vxlan_anycast_ip

        return self.utils.default_to_dict(_loopback)

    def _vlans(self):
        vlans = self.utils.load_masterfile('vlans')
        existing_vlans = self.utils.load_datafile('vlans')

        self.check.vlans(
            existing_vlans, [item for k, v in vlans.items() for item in v]
            )

        # def _transport_vni():
        #     vids = iter(
        #         self.utils.difference(range(4000, 4091), [
        #             int(id) for id, value in existing_vlans.items()
        #             if value['name'] == 'transport_vni'])
        #         )
        #     for id in vids:
        #         yield str(id)
        #
        # vni = _transport_vni()

        vni = iter(
            self.utils.difference(range(4000, 4091), [
                int(id) for id, value in existing_vlans.items()
                if value['name'] == 'transport_vni'])
            )

        tenants = (
            [value['tenant'] for vid, value in existing_vlans.items()
                if value['name'] == 'transport_vni']
            )

        _vlans = {}
        for tenant, value in vlans.items():
            for vlan in value:
                _vlans[vlan['id']] = {
                    'tenant': tenant, 'name': vlan['name'], 'type': 'l2'
                    }
            if tenant not in tenants:
                _vlans[next(vni)] = {
                    'tenant': tenant, 'name': 'transport_vni', 'type': 'l3'
                    }

        for vid, value in existing_vlans.items():
            if (value['name'] == 'transport_vni'
                    and value['tenant'] in vlans.keys()):
                _vlans[vid] = value

        # # Add public vlan
        # _vlans['2'] = {
        #     'name': 'public vlan',
        #     'subnet': '10.128.0.0/16'
        # }

        return self.utils.dump_datafile('vlans', _vlans)

    def _clag_interface(self):
        mlag = self.utils.load_masterfile('mlag_bonds')
        clag_interface = self.utils.load_datafile('clag_interface')

        for rack in mlag:
            try:
                existing_ids = clag_interface[rack].values()
            except KeyError:
                existing_ids = [0]

            available_ids = self.utils.difference(
                range(1, 100), existing_ids)

            loop = 0
            for index, item in enumerate(mlag[rack], start=1):
                try:
                    if item['name'] not in clag_interface[rack].keys():
                        clag_interface[rack].update(
                            {item['name']: available_ids[loop]}
                            )
                        loop += 1
                except KeyError:
                    clag_interface[rack] = {
                        item['name']: available_ids[loop]
                        }
                    loop += 1

            for rack, bonds in clag_interface.copy().items():
                if rack not in mlag.keys():
                    clag_interface.pop(rack)
                try:
                    for bond in bonds.copy().keys():
                        if bond not in [item['name'] for item in mlag[rack]]:
                            clag_interface[rack].pop(bond)
                except KeyError:
                    pass

        return self.utils.dump_datafile('clag_interface', clag_interface)

    def _mlag_peerlink(self):
        mlag_peerlink_interface = self.utils.load_masterfile(
            'mlag_peerlink_interface')

        clag = {}
        for host in self._groups('leaf'):
            host_id = self._host_id(host)
            rack_id = self._rack_id(host)
            loopback_ipv4_address = self._loopback_ipv4_address(host)
            system_mac = (
                self.utils.mac_address('44:38:39:FF:01:00', -(rack_id))
                )

            if host_id % 2 == 0:
                clag_role = '2000'
                backup_ip = (
                    self.utils.get_address(loopback_ipv4_address, -1)
                    )
                peer_ip = '169.254.1.1'
                ip = '169.254.1.2/30'
            else:
                clag_role = '1000'
                backup_ip = (
                    self.utils.get_address(loopback_ipv4_address, +1)
                    )
                peer_ip = '169.254.1.2'
                ip = '169.254.1.1/30'

            peerlink_interface = sorted(self.utils.unique(
                self.utils.cluster_to_range(mlag_peerlink_interface))
                )

            clag[host] = {
                'priority': clag_role,
                'system_mac': system_mac,
                'interface': ",".join(peerlink_interface),
                'backup_ip': backup_ip,
                'peer_ip': peer_ip, 'ip': ip
                }

        return clag

    def mlag(self):
        mlag = self.utils.load_masterfile('mlag_bonds')
        vlans = self._vlans()
        clag_interface = self._clag_interface()
        mlag_peer = self._mlag_peerlink()
        self.check.mlag_bonds(vlans, mlag)

        bonds = defaultdict(lambda: defaultdict(dict))
        for rack in mlag:
            _members = []
            for item in mlag[rack]:
                vids = self.utils.unique(
                    self.utils.cluster_to_range(item['vids']))
                alias = self.utils.range_cluster(
                    [vlans[vid]['name'] for vid in vids])
                tenant = "".join(
                    self.utils.unique([vlans[vid]['tenant'] for vid in vids]))

                members = sorted(self.utils.unique(
                    self.utils.cluster_to_range(item['members'])))
                _members.extend(members)
                type = 'trunk' if len(vids) > 1 else 'access'
                clag_id = clag_interface[rack][item['name']]

                bonds[rack][item['name']] = {
                    'vids': self.utils.range_to_cluster(vids),
                    'clag_id': clag_id,
                    'alias': "{}: {}".format(tenant, alias),
                    'tenant': tenant,
                    'members': ",".join(members),
                    'type': type
                    }

        _bonds = self.utils.default_to_dict(bonds)
        _mlag = defaultdict(lambda: defaultdict(dict))

        for host in self._groups('leaf'):
            rack_name = self._rack_id(host, 'name')
            if rack_name in _bonds:
                _mlag[host]['bonds'] = _bonds[rack_name]
                _mlag[host]['peer'] = mlag_peer[host]

        return self.utils.default_to_dict(_mlag)

    def _vlans_subnet(self):
        vlans = self.utils.load_masterfile('vlans')
        vlans_subnet = self.utils.load_datafile('vlans_subnet')

        # Delete VLANs not in file
        for vid in vlans_subnet.copy().keys():
            if vid not in ([
                    item['id'] for _, v in vlans.items() for item in v
                    ]):
                vlans_subnet.pop(vid)

        defined_subnets = (
            [item for k, v in vlans.items() for item in v if 'subnet' in item]
            )

        # Check defined subnets not overlaps or duplicate with existing subnets
        for item in defined_subnets:
            id = item['id']
            if (id in vlans_subnet.keys()
                    and item['subnet'] != vlans_subnet[id]['subnet']):
                self.check.vlans_subnet(
                    data=('vlans', id, item['subnet']),
                    existing_vlans=vlans_subnet
                    )
                vlans_subnet[id]['subnet'] = item['subnet']
            if id not in vlans_subnet.keys():
                self.check.vlans_subnet(
                    data=('vlans', id, item['subnet']),
                    existing_vlans=vlans_subnet
                    )
                vlans_subnet[id] = {
                    'subnet': item['subnet'], 'allocation': 'manual'
                    }

        base_net_prefix = self.load_masterfile('base_networks')['vlans']
        existing_subnets = [v['subnet'] for k, v in vlans_subnet.items()]

        defined_subnet_size = [
            item for k, v in vlans.items()
            for item in v if 'subnet_size' in item]

        sorted_subnet_size = (
            sorted(defined_subnet_size, key=itemgetter('subnet_size'))
            )

        for item in sorted_subnet_size:
            subnet = self.utils.get_subnet(
                base_net_prefix, existing_subnets, item['subnet_size'])

            if item['id'] not in vlans_subnet.keys():
                vlans_subnet[item['id']] = {
                    'subnet': next(subnet),
                    'allocation': 'auto_subnet_size',
                    'size': int(item['subnet_size'])
                    }

            if (item['id'] in vlans_subnet.keys()
                and vlans_subnet[item['id']]['allocation'] != 'auto_subnet_size'
                    or vlans_subnet[item['id']]['size'] != int(item['subnet_size'])):
                vlans_subnet[item['id']].update({
                    'subnet': next(subnet),
                    'allocation': 'auto_subnet_size',
                    'size': int(item['subnet_size'])
                     })

        subnet = self.utils.get_subnet(
            base_net_prefix, existing_subnets)

        undefined_subnet = [
            item for k, v in vlans.items() for item in v
            if 'subnet' not in item and 'subnet_size' not in item]

        try:
            for item in undefined_subnet:
                if item['id'] not in vlans_subnet.keys():
                    vlans_subnet[item['id']] = {
                        'subnet': next(subnet),
                        'allocation': 'auto_subnet'
                        }
                if (item['id'] in vlans_subnet.keys()
                        and vlans_subnet[item['id']]['allocation'] != 'auto_subnet'):
                    vlans_subnet[item['id']].update({
                        'subnet': next(subnet),
                        'allocation': 'auto_subnet'
                         })
        except StopIteration:
            raise AnsibleError('Run out of subnets.')

        # for vid in vlans_subnet.copy().keys():
        #     if vid not in ([
        #             item['id'] for _, v in vlans.items() for item in v
        #             ]):
        #         vlans_subnet.pop(vid)

        return self.utils.dump_datafile('vlans_subnet', vlans_subnet)

    def _host_vlans(self):
        mlag = self.mlag()
        vlans = self._vlans()

        _host_vlans = defaultdict(dict)
        for host in self._groups('border') + self._groups('leaf'):
            if host in mlag.keys():
                bonds = mlag[host]['bonds']
                vids = list(set(
                    [x for _, v in bonds.items()
                     for x in self.utils.cluster_to_range(v['vids'])
                     ]))
                tenants = self.utils.unique(
                    [vlans[vid]['tenant'] for vid in vids])

                for vid, value in vlans.items():
                    if (value['name'] == 'transport_vni'
                            and value['tenant'] in tenants):
                        vids.append(vid)
                for vid in vids:
                    _host_vlans[host].update({vid: vlans[vid]})

            else:
                for vid, value in vlans.items():
                    if (value['name'] == 'transport_vni'
                            and value['tenant']):
                        _host_vlans[host].update({vid: value})

        return dict(_host_vlans)

    def vxlan(self):
        host_vlans = self._host_vlans()
        base_name = 'vni'
        vxlan = defaultdict(lambda: defaultdict(dict))
        for host in host_vlans:
            # host_id = self._host_id(host)
            vxlan[host]['local_tunnelip'] = (
                self.utils.get_address(self._loopback_ipv4_address(host))
                )
            for vid, value in host_vlans[host].items():
                name = "{}{}".format(base_name, vid)
                vxlan[host]['vxlan'][[name]] = {
                    'tenant': value['tenant'],
                    'id': vid,
                    'vlan': vid,
                    'type': value['type']
                }

        return self.utils.default_to_dict(vxlan)

    def svi(self):
        host_vlans = self._host_vlans()
        vlan_subnets = self._vlans_subnet()

        svi = defaultdict(lambda: defaultdict(dict))
        for host, vids in host_vlans.items():
            if host in self._groups('leaf'):
                host_id = self._host_id(host)
                rack_id = self._rack_id(host)

                for vid, value in vids.items():
                    if value['type'] == 'l2':
                        virtual_mac = (
                            self.utils.mac_address('44:38:39:FF:01:00', vid)
                            )
                        virtual_address = (
                            self.utils.get_ip(vlan_subnets[vid]['subnet'], -2)
                            )
                        address = (
                            self.utils.get_ip(
                                vlan_subnets[vid]['subnet'], -(int(host_id + 2)
                                                               ))
                            )
                        svi[host][vid] = {
                            'virtual_mac': virtual_mac,
                            'virtual_address': virtual_address,
                            'address': address,
                            'tenant': value['tenant'],
                            'type': value['type']
                            }
                    if value['type'] == 'l3':
                        router_mac = (
                            self.utils.mac_address(
                                '44:39:39:FF:FF:FF', -(rack_id))
                                )
                        svi[host][vid] = {
                            'tenant': value['tenant'],
                            'router_mac': router_mac,
                            'type': value['type']
                            }
            else:
                svi[host] = vids

        return self.utils.default_to_dict(svi)

    def _links(self, link, slice=False):
        # Return list of tuples of permutations of link base on Ansible Inventory
        # Argument format:'group/host:staring_port -- group/host:staring_port'
        # group and host must exist in ansible inventory
        # Ex. 'spine:swp1 -- leaf:swp21'
        # Return values: [(spine01, swp1, leaf01, swp21), leaf01, swp21, spine01, swp1]
        _link = permutations(
            [i for item in link.split('--') for i in item.strip().split(':')]
            )
        t = []
        for item in list(_link)[0::16]:
            dev_a, a_port, dev_b, b_port = item

            data = (
                sorted(self._groups(dev_a)),
                self.utils.ifrange(a_port, len(self._groups(dev_b))),
                sorted(self._groups(dev_b)),
                self.utils.ifrange(b_port, len(self._groups(dev_a)))
            )

            hosts, ports, nei, nei_ports = data

            for h in range(len(hosts)):
                for n in range(len(nei)):
                    t.append((hosts[h], ports[n], nei[n], nei_ports[h]))

        if slice:
            return iter(t[:len(t)//2])
        else:
            return iter(t)

    # def _links(self, links):
    #     _links = {}
    #     for name, links in links.items():
    #         links_list = defaultdict(list)
    #         for link in links:
    #             links_perm = (
    #                 permutations([item.strip() for item in link.split('--')])
    #                 )
    #             for item in links_perm:
    #                 links_ = (
    #                     tuple([y for x in item for y in x.split(':')])
    #                     )
    #
    #                 grp, iface, nei_grp, nei_iface = links_
    #
    #                 try:
    #                     hosts = sorted(self._groups(grp))
    #                     nei_hosts = sorted(self._groups(nei_grp))
    #                     num_of_hosts = len(hosts)
    #                     num_of_nei = len(nei_hosts)
    #
    #                     iface_id = self.utils.interface(iface)
    #                     _iface_range = (
    #                         "{}-{}".format(iface, iface_id + num_of_nei - 1)
    #                         )
    #                     iface_range = self.utils.cluster_to_range(_iface_range)
    #
    #                     nei_iface_id = self.utils.interface(nei_iface)
    #                     _nei_iface_range = (
    #                         "{}-{}".format(
    #                             nei_iface, nei_iface_id + num_of_hosts - 1)
    #                             )
    #                     nei_iface_range = (
    #                         self.utils.cluster_to_range(_nei_iface_range)
    #                         )
    #
    #                     if grp == link.split(':')[0]:
    #                         in_item = (
    #                             "{}:{} -- {}:{}".format(
    #                                 grp,
    #                                 self.utils.range_to_cluster(iface_range),
    #                                 nei_grp,
    #                                 self.utils.range_to_cluster(
    #                                     nei_iface_range)
    #                                 )
    #                             )
    #                     else:
    #                         in_item = (
    #                             "{}:{} -- {}:{}".format(
    #                                 nei_grp,
    #                                 self.utils.range_to_cluster(
    #                                     nei_iface_range),
    #                                 grp,
    #                                 self.utils.range_to_cluster(iface_range)
    #                                 )
    #                             )
    #
    #                     links_list[grp].append({
    #                         'hosts': hosts,
    #                         'nei_hosts': nei_hosts,
    #                         'nei_grp': nei_grp,
    #                         'iface_range': iface_range,
    #                         'nei_iface_range': nei_iface_range,
    #                         'num_of_hosts': num_of_hosts,
    #                         'num_of_nei': num_of_nei,
    #                         'in_item': in_item
    #                         })
    #                 except KeyError:
    #                     if grp == link.split(':')[0]:
    #                         in_item = (
    #                             "{}:{} -- {}:{}".format(
    #                                 grp, iface, nei_grp, nei_iface)
    #                             )
    #                     else:
    #                         in_item = (
    #                             "{}:{} -- {}:{}".format(
    #                                 nei_grp, nei_iface, grp, iface)
    #                             )
    #                     links_list[grp].append({
    #                         'iface': iface,
    #                         'link_to': nei_grp,
    #                         'r_iface': nei_iface,
    #                         'in_item': in_item,
    #                     })
    #         _links[name] = dict(links_list)
    #
    #     self.check.links(_links)
    #
    #     return _links
    #
    # def interfaces_unnumbered(self):
    #     fabric = {'fabric': self.utils.load_masterfile('fabric')}
    #     links = self._links(fabric)
    #     interfaces_unnum = defaultdict(dict)
    #     for _, v in links['fabric'].items():
    #         for item in v:
    #             for index, host in enumerate(item['hosts']):
    #                 for r in range(item['num_of_nei']):
    #                     iface = item['iface_range'][r]
    #                     interfaces_unnum[host][iface] = {
    #                         'remote_host': item['nei_hosts'][r],
    #                         'remote_port': item['nei_iface_range'][index],
    #                         'peer_group': item['nei_grp']
    #                         }
    #
    #     return interfaces_unnum

    # def interfaces_unnumbered(self):
    #     fabric = self.utils.load_masterfile('fabric')
    #     iface_unnum = defaultdict(lambda: defaultdict(dict))
    #     for item in fabric:
    #         links = self._links(item)
    #         host, iface, nhost, niface = links
    #         iface_unnum[host][iface] = {
    #             'host': nhost,
    #             'iface': niface,
    #             'peer'
    #         }
        # for _, v in links['fabric'].items():
        #     for item in v:
        #         for index, host in enumerate(item['hosts']):
        #             for r in range(item['num_of_nei']):
        #                 iface = item['iface_range'][r]
        #                 interfaces_unnum[host][iface] = {
        #                     'remote_host': item['nei_hosts'][r],
        #                     'remote_port': item['nei_iface_range'][index],
        #                     'peer_group': item['nei_grp']
        #                     }

        # return interfaces_unnum
    # def _interfaces_subnet(self):
    #     ptp_net = self.utils.load_masterfile('external_connectivity')
    #     base_net_prefix = '172.28.0.0/14'
    #     data = self.utils.load_datafile('external_subnets')
    #     try:
    #         if data['base_net_prefix'] != base_net_prefix:
    #                 data['base_net_prefix'] = base_net_prefix
    #                 data['subnets'] = {}
    #     except KeyError:
    #         data = {'base_net_prefix': base_net_prefix, 'subnets': {}}
    #
    #     subnet = self.utils.get_subnet(
    #         base_net_prefix, list(data['subnets'].keys()), 30)
    #     existing_vids = self.utils.unique(
    #         [value['vlan'] for _, value in data['subnets'].items()])
    #     existing_network_id = self.utils.unique(
    #         [value['network_id'] for _, value in data['subnets'].items()])
    #
    #     vids = {vid: value for vid, value in self._vlans().items()
    #             if value['name'] == 'transport_vni'}
    #
    #     for item in ptp_net:
    #         if item not in existing_network_id:
    #             for vid in vids.keys():
    #                 data['subnets'][next(subnet)] = {
    #                     'vlan': vid, 'network_id': item,
    #                     'vrf': vids[vid]['tenant']
    #                     }
    #         else:
    #             for vid in vids.keys():
    #                 if vid not in existing_vids:
    #                     data['subnets'][next(subnet)] = {
    #                         'vlan': vid, 'network_id': item,
    #                         'vrf': vids[vid]['tenant']
    #                         }
    #
    #     for subnet, value in data['subnets'].copy().items():
    #         if value['vlan'] not in vids.keys():
    #             data['subnets'].pop(subnet)
    #         if value['network_id'] not in ptp_net:
    #             data['subnets'].pop(subnet)
    #
    #     return self.utils.dump_datafile('external_subnets', data)

    def external_networks(self):
        base_net_prefix = self.utils.load_masterfile(
            'base_networks')['external_connectivity']
        external_conn = self.utils.load_datafile('external_networks')

        if external_conn['base_net_prefix'] != base_net_prefix:
            external_conn = (
                {'base_net_prefix': base_net_prefix, 'networks': {}}
                )
        get_subnet = self.utils.get_subnet(
            base_net_prefix, list(external_conn['networks'].keys()), 30)
        tvids = {vid: value for vid, value in self._vlans().items()
                 if value['name'] == 'transport_vni'}
        e_tvids = self.utils.unique(
            [v['vid'] for _, v in external_conn['networks'].items()])
        e_links = (
            [v['links'] for _, v in external_conn['networks'].items()]
            )

        _links = []
        for item in self.utils.load_masterfile('external_connectivity'):
            links = self._links(item, slice=True)
            for link in links:
                _link = [[link[0], link[1]], [link[2], link[3]]]
                _links.append(_link)
                for tvid in sorted(tvids.keys()):
                    if tvid not in e_tvids or _link not in e_links:
                        external_conn['networks'][next(get_subnet)] = {
                            'vid': tvid,
                            'links': _link,
                            'vrf': tvids[tvid]['tenant']
                        }

        for k, v in external_conn['networks'].copy().items():
            if v['vid'] not in tvids.keys() or v['links'] not in _links:
                external_conn['networks'].pop(k)

        return self.utils.dump_datafile('external_networks', external_conn)

    def interfaces_unnumbered(self):
        # Generate interfaces unnumebered base on fabric variable
        iface_unnum = defaultdict(lambda: defaultdict(dict))
        for item in self.utils.load_masterfile('fabric'):
            links = self._links(item)
            for link in links:
                host, iface, nhost, niface = link
                iface_unnum[host][iface] = {
                    'neighbor': {
                        'host': nhost,
                        'iface': niface,
                        'group': self._group_names(nhost)[0]
                    }
                }

        return iface_unnum

    def interfaces_ip(self):
        # External connectivity point-to-point networks
        interfaces_ip = defaultdict(lambda: defaultdict(dict))
        for k, v in self.external_networks()['networks'].items():
            for index, item in enumerate(v['links']):
                host, iface = item
                vif = '{}.{}'.format(iface, v['vid'])
                nhost = v['links'][index - 1][0]
                interfaces_ip[host][vif] = {
                    'address': self.utils.r_get_ip(k, index),
                    'neighbor': {
                        'host': nhost,
                        'interface': '{}.{}'.format(v['links'][index - 1][1], v['vid']),
                        'address': self.utils.r_get_ip(k, (index - 1)),
                        'group': self._group_names(nhost)[0]
                    }
                }

        return interfaces_ip

    # def interfaces_ip(self):
    #     external_subnets = self._interfaces_subnet()['subnets']
    #     ex_con = {'external_connectivity': self.utils.load_masterfile(
    #         'external_connectivity')}
    #     links = self._links(ex_con)
    #     interfaces_ip = defaultdict(dict)
    #     for host, value in links['external_connectivity'].items():
    #         for item in value:
    #             y = [i.strip()
    #                  for i in item['in_item'].replace('--', ':').split(':')]
    #             node, iface, neig, niface = y
    #             for subnet, value in external_subnets.items():
    #                 if value['network_id'] == item['in_item']:
    #                     ip_index = 1 if host in node else 2
    #                     remote_ip_index = 2 if host in node else 1
    #                     ip = self.utils.get_ip(subnet, ip_index)
    #                     remote_ip = self.utils.get_ip(subnet, remote_ip_index)
    #                     vif = "{}.{}".format(item['iface'], value['vlan'])
    #                     remote_iface = "{}.{}".format(
    #                         item['r_iface'], value['vlan'])
    #                     interfaces_ip[host][vif] = {
    #                         'remote_host': item['link_to'],
    #                         'remote_intf': remote_iface,
    #                         'ipv4_address': ip,
    #                         'vrf': value['vrf'],
    #                         'remote_ipv4_address': remote_ip
    #                     }

    # def bgp(self):
    #     bgp_base_asn = self.utils.load_masterfile('bgp_base_asn')
    #     common = {}
    #
    #     intf_unnum = self.interfaces_unnumbered()
    #     intf_ip = self.interfaces_ip()
    #
    #     bgp_neighbors = defaultdict(
    #         lambda: defaultdict(lambda: defaultdict(list)))
    #     for group, asn in bgp_base_asn.items():
    #         for host in self._groups(group):
    #             host_id = self._host_id(host)
    #             lo = self._loopback_ipv4_address(host)
    #             router_id = self.utils.get_address(lo)
    #             if host in self._groups('spine'):
    #                 _asn = asn
    #             else:
    #                 _asn = asn + host_id - 1
    #
    #             common[host] = {'asn': _asn, 'router_id': router_id}
    #
    #     for host in intf_unnum:
    #         _bgp_neighbors = bgp_neighbors[host]['global']
    #         _bgp_neighbors['router_id'] = common[host]['router_id']
    #         _bgp_neighbors['as'] = common[host]['asn']
    #
    #         for intf, v in intf_unnum[host].items():
    #             _bgp_neighbors['neighbors'].append({
    #                 'neighbor': intf,
    #                 'as': 'external',
    #                 'group': v['peer_group'],
    #                 'host': v['remote_host'],
    #                 'id': common[v['remote_host']]['router_id']
    #             })
    #
    #     for host in intf_ip:
    #         for intf, v in intf_ip[host].items():
    #             _bgp_neighbors = bgp_neighbors[host][v['vrf']]
    #             _bgp_neighbors['router_id'] = common[host]['router_id']
    #             _bgp_neighbors['as'] = common[host]['asn']
    #
    #             _bgp_neighbors['neighbors'].append({
    #                 'neighbor': v['remote_ipv4_address'].split('/')[0],
    #                 'host': v['remote_host'],
    #                 'as': common[v['remote_host']]['asn'],
    #                 'id': common[v['remote_host']]['router_id'],
    #                 })
    #
    #     return self.utils.default_to_dict(bgp_neighbors)
    #
    # def interfaces_list(self):
    #     intfs_list = defaultdict(dict)
    #
    #     interfaces = {
    #         'external_connectivity': self.interfaces_ip(),
    #         'fabric': self.interfaces_unnumbered(),
    #         'mlag': self.mlag()
    #     }
    #
    #     for host, intfs in interfaces['external_connectivity'].items():
    #         sub_intfs = self.utils.unique(
    #             [item.split('.')[0] for item in intfs.keys() if '.' in item])
    #         intfs_list[host].update({'external_connectivity': sub_intfs})
    #
    #     for host, intfs in interfaces['fabric'].items():
    #             intfs_list[host].update({'fabric': list(intfs.keys())})
    #
    #     for host, clag in interfaces['mlag'].items():
    #         peerlink = self.utils.cluster_to_range(
    #             clag['peer']['interface'])
    #         members = []
    #         for bond, v in clag['bonds'].items():
    #             for member in self.utils.cluster_to_range(v['members']):
    #                 members.append(member)
    #         intfs_list[host].update({'mlag_peerlink_interface': peerlink})
    #         intfs_list[host].update({'mlag_bonds': members})
    #
    #     self.check.interfaces_list(intfs_list)
    #
    # def ptm(self):
    #     ext_con = self.utils.load_masterfile('external_connectivity')
    #     fabric = self.utils.load_masterfile('fabric')
    #     links = self._links(fabric)
    #     ptm = {'ptm': []}
    #     for group, value in links.items():
    #         for item in value:
    #             if item['in_item'].split(':')[0] == group:
    #                 for index, host in enumerate(item['hosts']):
    #                     for r in range(item['num_of_nei']):
    #                         ptm['ptm'].append('"{}":"{}" -- "{}":"{}"'.format(
    #                             host, item['iface_range'][r],
    #                             item['nei_hosts'][r],
    #                             item['nei_iface_range'][index]
    #                         ))
    #
    #     for item in ext_con:
    #         _ext_con = [x.strip() for x in item.replace('--', ':').split(':')]
    #         host, iface, nei_host, nei_iface = _ext_con
    #         _ptm_format = '"{}":"{}" -- "{}":"{}"'.format(host, iface,
    #                                                       nei_host, nei_iface)
    #         ptm['ptm'].append(_ptm_format)
    #
    #     file_sys_loader = FileSystemLoader('templates')
    #     env = Environment(loader=file_sys_loader)
    #     template = env.get_template('ptm.j2')
    #
    #     output = template.render(ptm=ptm)
    #     with open("files/ptm.dot", 'w') as f:
    #         f.write(output)
    #     return output
    #
    # def nat_rules(self):
    #     vlans_subnet = self._vlans_subnet()
    #
    #     nat_rules = self.utils.load_datafile('nat')
    #
    #     def nat_rule():
    #         rules = self.utils.difference(range(5000, 9000), [
    #             item['rule'] for item in nat_rules])
    #
    #         for rule in sorted(rules):
    #             yield rule
    #
    #     rule = nat_rule()
    #
    #     for k, v in vlans_subnet.items():
    #         if v['subnet'] not in [
    #                 item['source_address'] for item in nat_rules
    #                 ]:
    #             nat_rules.append({
    #                 'name': 'vlan' + k,
    #                 'rule': next(rule),
    #                 'source_address': v['subnet']
    #             })
    #
    #     for item in nat_rules.copy():
    #         id = item['name'].split('vlan')[0]
    #         try:
    #             if vlans_subnet[id]['subnet'] != item['source_address']:
    #                 nat_rules.remove(item)
    #         except KeyError:
    #             pass
    #
    #     return nat_rules
