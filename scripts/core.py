#!/usr/bin/python
from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager
from ansible.vars.manager import VariableManager
from ansible.vars.hostvars import HostVars
from jinja2 import Environment, FileSystemLoader
from operator import itemgetter
from collections import defaultdict
from itertools import permutations
import utilities
import checkvars
import os
import re

utils = utilities.Utilities()
chkvars = checkvars.CheckVars()


# Class that generates ansible variables needed to configure Cumulus VxLAN EVPN.
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

    def _groups(self, name='network_device'):
        return self.inventory.get_groups_dict()[name]

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

    def _loopback_ipv4_address(self, host):
        base_subnet = utils.load_masterfile(
            'loopback_ipv4_base_subnet')

        for group, subnet in base_subnet.items():
            if host in self._groups(group):
                host_id = self._host_id(host)
                return utils.get_ip(
                    subnet, host_id, 'loopback'
                )

    def loopback(self):
        base_subnet = utils.load_masterfile(
            'loopback_ipv4_base_subnet')
        clag_vxlan_anycast_base_subnet = utils.load_masterfile(
            'mlag_vxlan_anycast_base_subnet')

        lo = {}
        for group, subnet in base_subnet.items():
            for host in self._groups(group):
                lo[host] = {
                    'ip_addresses': [], 'clag_vxlan_anycast_ip': None
                    }
                host_id = self._host_id(host)
                rack_id = self._rack_id(host)
                ip = self._loopback_ipv4_address(host)

                lo[host]['ip_addresses'].append(ip)
                # lo[host]['allentries'].extend([ip, '127.0.0.1/8', '::1/128'])

                if host in self._groups('leaf'):
                    vxlan_anycast_ip = utils.get_ip(
                        clag_vxlan_anycast_base_subnet, rack_id, 'address')

                    lo[host]['clag_vxlan_anycast_ip'] = vxlan_anycast_ip
                    # lo[host]['allentries'].append(vxlan_anycast_ip)

        return utils.default_to_dict(lo)

    def _vlans(self):
        mf_vlans = utils.load_masterfile('vlans')
        df_vlans = utils.load_datafile('vlans')

        chkvars.vlans()

        def _transport_vni():
            vids = utils.difference(range(4000, 4091), [
                                int(id) for id, value in df_vlans.items()
                                if value['name'] == 'transport_vni'])
            for id in vids:
                yield str(id)

        vni = _transport_vni()

        tenants = [value['tenant'] for vid, value in df_vlans.items()
                   if value['name'] == 'transport_vni']

        _vlans = {}
        for tenant, value in mf_vlans.items():
            for vlan in value:
                _vlans[vlan['id']] = {
                    'tenant': tenant, 'name': vlan['name'], 'type': 'l2'
                    }

            if tenant not in tenants:
                _vlans[next(vni)] = {
                    'tenant': tenant, 'name': 'transport_vni', 'type': 'l3'
                    }

        for vid, value in df_vlans.items():
            if (value['name'] == 'transport_vni'
                    and value['tenant'] in mf_vlans.keys()):
                _vlans[vid] = value

        if _vlans == df_vlans:
            return df_vlans
        else:
            return utils.dump_datafile('vlans', _vlans)

    def _clag_interface(self):
        mlag = utils.load_masterfile('mlag_bonds')
        clag_interface = utils.load_datafile('clag_interface')

        for rack in mlag:
            try:
                existing_ids = clag_interface[rack].values()
            except KeyError:
                existing_ids = [0]

            available_ids = utils.difference(
                range(1, 100), existing_ids)

            loop = 0
            for index, item in enumerate(mlag[rack], start=1):
                try:
                    if item['name'] not in clag_interface[rack].keys():
                        clag_interface[rack].update({
                            item['name']: available_ids[loop]
                            })
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
                    for bond in bonds.keys():
                        if bond not in [item['name'] for item in mlag[rack]]:
                            clag_interface[rack].pop(bond)
                except KeyError:
                    pass

        return utils.dump_datafile('clag_interface', clag_interface)

    def _mlag_peerlink(self):
        mlag_peerlink_interface = utils.load_masterfile(
            'mlag_peerlink_interface')

        clag = {}
        for host in self._groups('leaf'):
            host_id = self._host_id(host)
            rack_id = self._rack_id(host)
            loopback_ipv4_address = self._loopback_ipv4_address(host)
            system_mac = utils.mac_address(
                '44:38:39:FF:01:00', -(rack_id)
                )

            if host_id % 2 == 0:
                clag_role = 'secondary'
                backup_ip = utils.get_address(
                            loopback_ipv4_address, -1)
            else:
                clag_role = 'primary'
                backup_ip = utils.get_address(
                    loopback_ipv4_address, +1)

            peerlink_interface = utils.range_cluster(utils.unique(
                utils.cluster_to_range(mlag_peerlink_interface)))

            clag[host] = {'role': clag_role, 'system_mac': system_mac,
                          'peerlink_interface': peerlink_interface,
                          'backup_ip': backup_ip,
                          }

        return clag

    def mlag(self):
        mlag = utils.load_masterfile('mlag_bonds')
        vlans = self._vlans()
        clag_interface = self._clag_interface()
        mlag_peer = self._mlag_peerlink()
        chkvars.mlag_bonds(vlans, mlag)

        bonds = defaultdict(lambda: defaultdict(dict))
        for rack in mlag:
            _members = []
            for item in mlag[rack]:
                vids = utils.unique(
                    utils.cluster_to_range(item['vids']))
                alias = ",".join(
                    [vlans[vid]['name'] for vid in vids])
                tenant = "".join(
                    utils.unique([vlans[vid]['tenant'] for vid in vids]))

                members = utils.unique(utils.cluster_to_range(item['members']))
                _members.extend(members)
                type = 'trunk' if len(vids) > 1 else 'access'
                clag_id = clag_interface[rack][item['name']]

                bonds[rack][item['name']] = {
                    'vids': utils.range_to_cluster(vids),
                    'clag_id': clag_id,
                    'alias': "{}: {}".format(tenant, alias),
                    'tenant': tenant,
                    'members': utils.range_cluster(members),
                    'type': type
                    }

            # bonds[rack]['summary'].update(
            #     {'members': utils.range_cluster(_members)})

        _bonds = utils.default_to_dict(bonds)
        _mlag = defaultdict(lambda: defaultdict(dict))
        for host in self._groups('leaf'):
            rack_name = self._rack_id(host, 'name')
            if rack_name in _bonds:
                _mlag[host]['bonds'] = _bonds[rack_name]
                _mlag[host]['peer'] = mlag_peer[host]

        return utils.default_to_dict(_mlag)

    def _vlan_subnets(self):
        vlans = utils.load_masterfile('vlans')
        vlan_subnets = utils.load_datafile('vlan_subnets')
        _vlans = utils.flatten(list(vlans.values()))

        defined_subnets = []
        for item in _vlans:
            if ('subnet' in item
                    and (item['id'] in vlan_subnets.keys()
                         and item['subnet'] != vlan_subnets[item['id']])):
                del vlan_subnets[item['id']]
                defined_subnets.append(item)
            if ('subnet' in item
                    and item['id'] not in vlan_subnets.keys()):
                defined_subnets.append(item)

        new_subnets = [item['subnet'] for item in defined_subnets]
        chkvars.vlan_subnets(
            new_subnets, vlan_subnets, self._vlans())
        for item in defined_subnets:
            vlan_subnets[item['id']] = {'subnet': item['subnet'],
                                        'allocation': 'manul'
                                        }

        existing_subnets = utils.map_attr(
            'subnet', list(vlan_subnets.values())
            )
        base_vlan_network = utils.load_masterfile('vlan_base_net_prefix')

        defined_subnet_size = [
            item for item in _vlans if 'subnet_size' in item]
        sorted_subnet_size = sorted(defined_subnet_size,
                                    key=itemgetter('subnet_size'))
        for item in sorted_subnet_size:
            subnet = utils.get_subnet(
                base_vlan_network, existing_subnets, item['subnet_size'])
            if item['id'] not in vlan_subnets.keys():
                vlan_subnets[item['id']] = {'subnet': next(subnet),
                                            'allocation': 'auto_subnet_size'
                                            }
            if (item['id'] in vlan_subnets.keys()
                    and vlan_subnets[item['id']]['allocation'] != 'auto_subnet_size'):
                del vlan_subnets[item['id']]
                vlan_subnets[item['id']] = {'subnet': next(subnet),
                                            'allocation': 'auto_subnet_size'
                                            }
        existing_subnets = utils.map_attr(
            'subnet', list(vlan_subnets.values()))
        subnet = utils.get_subnet(
            base_vlan_network, existing_subnets)
        undefined_subnet = [
            item for item in _vlans
            if 'subnet' not in item and 'subnet_size' not in item
            ]
        for item in undefined_subnet:
            if item['id'] not in vlan_subnets.keys():
                vlan_subnets[item['id']] = {'subnet': next(subnet),
                                            'allocation': 'auto_subnet'
                                            }
            if (item['id'] in vlan_subnets.keys()
                    and vlan_subnets[item['id']]['allocation'] != 'auto_subnet'):
                del vlan_subnets[item['id']]
                vlan_subnets[item['id']] = {'subnet': next(subnet),
                                            'allocation': 'auto_subnet'
                                            }

        for vid in vlan_subnets.copy().keys():
            if vid not in utils.map_attr('id', _vlans):
                vlan_subnets.pop(vid)

        if vlan_subnets == utils.load_datafile('vlan_subnets'):
            return vlan_subnets
        else:
            return utils.dump_datafile('vlan_subnets', vlan_subnets)

    def _host_vlans(self):
        mlag = self.mlag()
        vlans = self._vlans()

        _host_vlans = defaultdict(dict)
        for host in self._groups('border') + self._groups('leaf'):
            if host in mlag.keys():
                bonds = mlag[host]['bonds']
                vids = list(set(
                    [x for _, v in bonds.items()
                     for x in utils.cluster_to_range(v['vids'])
                     ]))
                tenants = utils.unique(
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

        vxlan = defaultdict(lambda: defaultdict(dict))
        for host in host_vlans:
            # host_id = self._host_id(host)
            vxlan[host]['local_tunnelip'] = utils.get_address(
                self._loopback_ipv4_address(host))
            for vid, value in host_vlans[host].items():
                name = "vni{}".format(vid)

                vxlan[host]['vxlan'][name] = {'tenant': value['tenant'],
                                              'id': vid,
                                              'vlan': vid,
                                              'type': value['type']
                                              }

        return utils.default_to_dict(vxlan)

    def svi(self):
        host_vlans = self._host_vlans()
        vlan_subnets = self._vlan_subnets()

        svi = defaultdict(lambda: defaultdict(dict))
        for host, vids in host_vlans.items():
            if host in self._groups('leaf'):
                host_id = self._host_id(host)
                rack_id = self._rack_id(host)
                for vid, value in vids.items():
                    if value['type'] == 'l2':
                        virtual_mac = utils.mac_address(
                            '44:38:39:FF:01:00', vid)
                        virtual_address = utils.get_ip(
                            vlan_subnets[vid]['subnet'], -2)
                        ip_index = -3 if host_id % 2 == 0 else -4
                        address = utils.get_ip(
                            vlan_subnets[vid]['subnet'], ip_index)

                        svi[host][vid] = {'virtual_mac': virtual_mac,
                                          'virtual_address': virtual_address,
                                          'address': address,
                                          'tenant': value['tenant'],
                                          'type': value['type']
                                          }
                    if value['type'] == 'l3':
                        router_mac = utils.mac_address(
                            '44:39:39:FF:FF:FF', -(rack_id))
                        svi[host][vid] = {'tenant': value['tenant'],
                                          'router_mac': router_mac,
                                          'type': value['type']
                                          }
            else:
                svi[host] = vids

        return utils.default_to_dict(svi)

    def _links(self, links):
        # links = utils.load_masterfile('fabric')
        _links = defaultdict(list)
        for link in links:
            links_perm = permutations(
                [item.strip() for item in link.split('--')]
                )

            for item in links_perm:
                links_ = tuple(
                    [y for x in item for y in x.split(':')])

                grp, iface, nei_grp, nei_iface = links_
                try:
                    hosts = sorted(self._groups(grp))
                    nei_hosts = sorted(self._groups(nei_grp))
                    num_of_hosts = len(hosts)
                    num_of_nei = len(nei_hosts)

                    iface_id = utils.interface(iface)
                    iface_range = utils.cluster_to_range(
                        "{}-{}".format(iface, iface_id + num_of_nei - 1))

                    nei_iface_id = utils.interface(nei_iface)
                    nei_iface_range = utils.cluster_to_range(
                        "{}-{}".format(nei_iface, nei_iface_id + num_of_hosts - 1))

                    if grp == link.split(':')[0]:
                        in_item = "{}:{} -- {}:{}".format(
                            grp, utils.range_to_cluster(iface_range),
                            nei_grp, utils.range_to_cluster(nei_iface_range)
                        )
                    else:
                        in_item = "{}:{} -- {}:{}".format(
                            nei_grp, utils.range_to_cluster(nei_iface_range),
                            grp, utils.range_to_cluster(iface_range)
                        )

                    _links[grp].append({
                        'hosts': hosts,
                        'nei_hosts': nei_hosts,
                        'nei_grp': nei_grp,
                        'iface_range': iface_range,
                        'nei_iface_range': nei_iface_range,
                        'num_of_hosts': num_of_hosts,
                        'num_of_nei': num_of_nei,
                        'in_item': in_item
                    })
                except KeyError:
                    if grp == link.split(':')[0]:
                        in_item = "{}:{} -- {}:{}".format(
                            grp, iface, nei_grp, nei_iface
                        )
                    else:
                        in_item = "{}:{} -- {}:{}".format(
                            nei_grp, nei_iface, grp, iface
                        )
                    _links[grp].append({
                        'iface': iface,
                        'link_to': nei_grp,
                        'r_iface': nei_iface,
                        'in_item': in_item,
                    })

        chkvars.links(dict(_links))

        return _links

    def interfaces_unnumbered(self):
        fabric = utils.load_masterfile('fabric')

        interfaces = defaultdict(dict)
        for _, v in self._links(fabric).items():
            # iface = utils.range_to_cluster(
            #         [x for item in value for x in item['iface_range']]
            #         )
            for item in v:
                for index, host in enumerate(item['hosts']):
                    for r in range(item['num_of_nei']):
                        iface = item['iface_range'][r]
                        interfaces[host][iface] = {
                            'remote_host': item['nei_hosts'][r],
                            'remote_port': item['nei_iface_range'][index],
                            'peer_group': item['nei_grp']
                            }

        # for host in unnumbered_iface:
        #     for peer, v in groupby(unnumbered_iface[host]['interfaces'], lambda x: x['peer_group']):
        #         iface_list = [item['interface'] for item in list(v)]
        #         unnumbered_iface[host]['summary'].append({
        #             'interfaces': utils.range_to_cluster(iface_list),
        #             'peer_group': peer, 'type': 'unnumbered_iface', 'address': None
        #         })

        return interfaces

    def _interfaces_subnet(self):
        ptp_net = utils.load_masterfile('external_connectivity')
        base_subnet = utils.load_masterfile('external_base_subnet')
        existing_subnets = utils.load_datafile('external_subnets')
        subnet = utils.get_subnet(
            base_subnet, list(existing_subnets.keys()), 30)
        existing_vids = utils.unique(
            [value['vlan'] for _, value in existing_subnets.items()]
            )
        existing_network_id = utils.unique(
            [value['network_id'] for _, value in existing_subnets.items()]
            )

        vids = {vid: value for vid, value in self._vlans().items()
                if value['name'] == 'transport_vni'}

        for item in ptp_net:
            if item not in existing_network_id:
                for vid in vids.keys():
                    existing_subnets[next(subnet)] = {
                        'vlan': vid, 'network_id': item,
                        'tenant': vids[vid]['tenant']
                        }
            else:
                for vid in vids.keys():
                    if vid not in existing_vids:
                        existing_subnets[next(subnet)] = {
                            'vlan': vid, 'network_id': item,
                            'tenant': vids[vid]['tenant']
                            }

        for subnet, value in existing_subnets.copy().items():
            if value['vlan'] not in vids.keys():
                existing_subnets.pop(subnet)
            if value['network_id'] not in ptp_net:
                existing_subnets.pop(subnet)

        return utils.dump_datafile('external_subnets', existing_subnets)

    def interfaces_ip(self):

        external_subnets = self._interfaces_subnet()
        links = self._links(utils.load_masterfile('external_connectivity'))
        chkvars.links(links)

        interfaces_ip = defaultdict(dict)
        for host, value in links.items():
            for item in value:
                for subnet, value in external_subnets.items():
                    if value['network_id'] == item['in_item']:
                        ip_index = 1 if host in self._groups('edge') else 2
                        remote_ip_index = 2 if host in self._groups(
                            'edge') else 1
                        ip = utils.get_ip(subnet, ip_index)
                        remote_ip = utils.get_ip(subnet, remote_ip_index)
                        vif = "{}.{}".format(item['iface'], value['vlan'])
                        remote_iface = "{}.{}".format(
                            item['r_iface'], value['vlan'])
                        interfaces_ip[host][vif] = {
                            'remote_host': item['link_to'],
                            'remote_intf': remote_iface,
                            'ipv4_address': ip,
                            'vrf': value['tenant'],
                            'remote_ipv4_address': remote_ip
                        }

        return interfaces_ip

    def bgp(self):
        bgp_base_asn = utils.load_masterfile('bgp_base_asn')
        common = {}

        intf_unnum = self.interfaces_unnumbered()
        intf_ip = self.interfaces_ip()
        bgp_neighbors = defaultdict(
            lambda: defaultdict(lambda: defaultdict(dict)))
        for group, asn in bgp_base_asn.items():
            for host in self._groups(group):
                host_id = self._host_id(host)
                lo = self._loopback_ipv4_address(host)
                router_id = utils.get_address(lo)
                if host in self._groups('spine'):
                    _asn = asn
                else:
                    _asn = asn + host_id - 1

                common[host] = {'asn': _asn, 'router_id': router_id}

        for host in intf_unnum:
            peer_groups = utils.unique([
                v['peer_group'] for intf, v in intf_unnum[host].items()
                ])
            bgp_neighbors[host]['global']['peer_groups'] = peer_groups
            for intf, v in intf_unnum[host].items():
                bgp_neighbors[host]['global']['router_id'] = common[host]['router_id']
                bgp_neighbors[host]['global']['as_number'] = common[host]['asn']
                bgp_neighbors[host]['global']['neighbors'][intf] = {
                    'remote_as': 'external',
                    'peer_group': v['peer_group'],
                    'remote_id': common[v['remote_host']]['router_id'],
                    'remote_peer': v['remote_host']
                    }

        for host in intf_ip:
            for intf, v in intf_ip[host].items():
                bgp_neighbors[host][v['vrf']]['router_id'] = router_id
                bgp_neighbors[host][v['vrf']
                                    ]['as_number'] = common[host]['asn']
                bgp_neighbors[host][v['vrf']]['neighbors'][v['remote_ipv4_address']] = {
                    'remote_as': common[v['remote_host']]['asn'],
                    'peer_group': v['remote_host'],
                    'remote_id': common[v['remote_host']]['router_id'],
                    'local_address': v['ipv4_address']
                    }

        return utils.default_to_dict(bgp_neighbors)

    def ptm(self):
        ext_con = utils.load_masterfile('external_connectivity')
        fabric = utils.load_masterfile('fabric')
        links = self._links(fabric)
        ptm = {'ptm': []}
        for group, value in links.items():
            for item in value:
                if item['in_item'].split(':')[0] == group:
                    for index, host in enumerate(item['hosts']):
                        for r in range(item['num_of_nei']):
                            ptm['ptm'].append('"{}":"{}" -- "{}":"{}"'.format(
                                host, item['iface_range'][r],
                                item['nei_hosts'][r],
                                item['nei_iface_range'][index]
                            ))

        for item in ext_con:
            _ext_con = [x.strip() for x in item.replace('--', ':').split(':')]
            host, iface, nei_host, nei_iface = _ext_con
            _ptm_format = '"{}":"{}" -- "{}":"{}"'.format(host, iface,
                                                          nei_host, nei_iface)
            ptm['ptm'].append(_ptm_format)

        file_sys_loader = FileSystemLoader('templates')
        env = Environment(loader=file_sys_loader)
        template = env.get_template('ptm.j2')

        output = template.render(ptm=ptm)
        with open("files/ptm.dot", 'w') as f:
            f.write(output)
        return output

    def dnsmasq(self):
        oob_mgmt_vars = utils.load_masterfile('oob_mgmt')
        hostvars = self._hostvars('mgmt_hwaddr')
