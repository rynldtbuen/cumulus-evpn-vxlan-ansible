# from ansible.errors import AnsibleError
from cl_vx_config.utils.checkconfig import CheckConfig as check
import cl_vx_config.utils as utils
# from cl_vx_config.utils.filters import Filters as f


mf = utils.File().master()
inv = utils.Inventory()


class GetConfig:

    def __init__(self):
        pass

    def loopbacks(self):
        # checkconfigvars.subnets()

        base_net = mf['base_networks']
        lo, clag = base_net['loopbacks'], base_net['vxlan_anycast']
        clag_net = utils.Network(clag)

        loopbacks = {}
        for group, subnet in lo.items():
            lo_net = utils.Network(subnet)
            for host in inv.hosts(group):
                h = utils.Host(host)
                loopbacks[host] = {
                    'ip_addresses': [], 'clag_vxlan_anycast_ip': None
                }

                lo_ip = lo_net.get_ip(h.node_id, lo=True)
                loopbacks[host]['ip_addresses'].append(lo_ip)

                if h in inv.hosts('leaf'):
                    loopbacks[host]['clag_vxlan_anycast_ip'] = (
                        clag_net.get_ip(h.rack_id, addr=True)
                    )

        return loopbacks

    def _l3vni(self):
        l3vni = utils.File('l3vni')

        x = [item for k, v in l3vni.data.items() for item in v.values()]
        existing_vnis = list(map(lambda x: x['id'], x))
        vnis = iter([r for r in range(4000, 4091) if r not in existing_vnis])

        for tenant in mf['vlans'].keys():
            if tenant not in l3vni.data.keys():
                vni = next(vnis)
                vlan = 'vlan' + str(vni)
                l3vni.data[tenant] = {
                    vlan: {'type': 'l3', 'id': vni, 'desc': 'l3vni'}}

        for tenant, v in l3vni.data.copy().items():
            if tenant not in mf['vlans'].keys():
                del l3vni.data[tenant]

        return l3vni.dump()

    def _vlans(self):
        check().vlans()

        vlans = self._l3vni()

        for tenant, value in mf['vlans'].items():
            for item in value:
                vlan = 'vlan' + item['id']
                vlans[tenant][vlan] = {
                    'type': 'l2', 'id': int(item['id']), 'desc': item['name']
                }

        return vlans

    # def _clag_interface(self):
    #
    #     clag_iface = File('clag_interface')
    #
    #     for rack in mlag:
    #         try:
    #             existing_ids = clag_interface[rack].values()
    #         except KeyError:
    #             existing_ids = [0]
    #
    #         available_ids = utils.difference(
    #             range(1, 100), existing_ids)
    #
    #         loop = 0
    #         for index, item in enumerate(mlag[rack], start=1):
    #             try:
    #                 if item['name'] not in clag_interface[rack].keys():
    #                     clag_interface[rack].update(
    #                         {item['name']: available_ids[loop]}
    #                         )
    #                     loop += 1
    #             except KeyError:
    #                 clag_interface[rack] = {
    #                     item['name']: available_ids[loop]
    #                     }
    #                 loop += 1
    #
    #         for rack, bonds in clag_interface.copy().items():
    #             if rack not in mlag.keys():
    #                 clag_interface.pop(rack)
    #             try:
    #                 for bond in bonds.copy().keys():
    #                     if bond not in [item['name'] for item in mlag[rack]]:
    #                         clag_interface[rack].pop(bond)
    #             except KeyError:
    #                 pass
    #
    #     return utils.dump_datafile('clag_interface', clag_interface)
    #
    # def mlag_peerlink(self):
    #     mlag_peerlink_interface = utils.load_masterfile(
    #         'mlag_peerlink_interface')
    #
    #     clag = {}
    #     for host in inv.groups('leaf'):
    #         host_id = self._host_id(host)
    #         rack_id = self._rack_id(host)
    #         loopback_ipv4_address = (
    #             self.loopbacks()[host]['ip_addresses'][0]
    #             )
    #         system_mac = (
    #             utils.mac_address('44:38:39:FF:01:00', -(rack_id))
    #             )
    #
    #         if host_id % 2 == 0:
    #             clag_role = '2000'
    #             backup_ip = (
    #                 utils.get_address(loopback_ipv4_address, -1)
    #                 )
    #             peer_ip = '169.254.1.1'
    #             ip = '169.254.1.2/30'
    #         else:
    #             clag_role = '1000'
    #             backup_ip = (
    #                 utils.get_address(loopback_ipv4_address, +1)
    #                 )
    #             peer_ip = '169.254.1.2'
    #             ip = '169.254.1.1/30'
    #
    #         peerlink_interface = sorted(utils.unique(
    #             utils.cluster_to_range(mlag_peerlink_interface))
    #             )
    #
    #         clag[host] = {
    #             'priority': clag_role,
    #             'system_mac': system_mac,
    #             'interface': ",".join(peerlink_interface),
    #             'backup_ip': backup_ip,
    #             'peer_ip': peer_ip, 'ip': ip
    #             }
    #
    #     return clag
    #
    # def mlag_bonds(self):
    #     return check().mlag_bonds()
    #     mlag = utils.load_masterfile('mlag_bonds')
    #     vlans = self._vlans()
    #     clag_interface = self._clag_interface()
    #     # mlag_peer = self._mlag_peerlink()
    #     checkconfigvars.mlag_bonds(vlans, mlag)
    #
    #     mlag_bonds = defaultdict(dict)
    #     for rack in mlag:
    #         _members = []
    #         for item in mlag[rack]:
    #             vids = utils.unique(
    #                 utils.cluster_to_range(item['vids']))
    #             alias = utils.range_cluster(
    #                 [vlans[vid]['name'] for vid in vids])
    #             tenant = "".join(
    #                 utils.unique([vlans[vid]['tenant'] for vid in vids]))
    #
    #             members = sorted(utils.unique(
    #                 utils.cluster_to_range(item['members'])))
    #             _members.extend(members)
    #             # type = 'trunk' if len(vids) > 1 else 'access'
    #             # clag_id = clag_interface[rack][item['name']]
    #
    #             mlag_bonds[rack][item['name']] = {
    #                 'vids': utils.range_to_cluster(vids),
    #                 'clag_id': clag_interface[rack][item['name']],
    #                 'alias': "{}: {}".format(tenant, alias),
    #                 'tenant': tenant,
    #                 'members': ",".join(members),
    #                 'type': 'trunk' if len(vids) > 1 else 'access'
    #                 }
    #
    #     return mlag_bonds
    #
    # def _vlans_subnet(self):
    #     vlans = utils.load_masterfile('vlans')
    #     vlans_subnet = utils.load_datafile('vlans_subnet')
    #
    #     # Delete VLANs not in datafile
    #     for vid in vlans_subnet.copy().keys():
    #         if vid not in ([
    #                 item['id'] for _, v in vlans.items() for item in v
    #                 ]):
    #             vlans_subnet.pop(vid)
    #
    #     defined_subnets = (
    #         [item for k, v in vlans.items() for item in v if 'subnet' in item]
    #         )
    #
    #     # Check defined subnets not overlaps or duplicate with existing subnets
    #     for item in defined_subnets:
    #         id = item['id']
    #         if (id in vlans_subnet.keys()
    #                 and item['subnet'] != vlans_subnet[id]['subnet']):
    #             checkconfigvars.vlans_subnet(
    #                 data=('vlans', id, item['subnet']),
    #                 existing_vlans=vlans_subnet
    #                 )
    #             vlans_subnet[id]['subnet'] = item['subnet']
    #         if id not in vlans_subnet.keys():
    #             checkconfigvars.vlans_subnet(
    #                 data=('vlans', id, item['subnet']),
    #                 existing_vlans=vlans_subnet
    #                 )
    #             vlans_subnet[id] = {
    #                 'subnet': item['subnet'], 'allocation': 'manual'
    #                 }
    #
    #     base_net_prefix = utils.load_masterfile('base_networks')['vlans']
    #     existing_subnets = [v['subnet'] for k, v in vlans_subnet.items()]
    #
    #     defined_subnet_size = [
    #         item for k, v in vlans.items()
    #         for item in v if 'subnet_size' in item]
    #
    #     sorted_subnet_size = (
    #         sorted(defined_subnet_size, key=itemgetter('subnet_size'))
    #         )
    #
    #     for item in sorted_subnet_size:
    #         subnet = utils.get_subnet(
    #             base_net_prefix, existing_subnets, item['subnet_size'])
    #
    #         if item['id'] not in vlans_subnet.keys():
    #             vlans_subnet[item['id']] = {
    #                 'subnet': next(subnet),
    #                 'allocation': 'auto_subnet_size',
    #                 'size': int(item['subnet_size'])
    #                 }
    #
    #         if (item['id'] in vlans_subnet.keys()
    #             and vlans_subnet[item['id']]['allocation'] != 'auto_subnet_size'
    #                 or vlans_subnet[item['id']]['size'] != int(item['subnet_size'])):
    #             vlans_subnet[item['id']].update({
    #                 'subnet': next(subnet),
    #                 'allocation': 'auto_subnet_size',
    #                 'size': int(item['subnet_size'])
    #                  })
    #
    #     subnet = utils.get_subnet(
    #         base_net_prefix, existing_subnets)
    #
    #     undefined_subnet = [
    #         item for k, v in vlans.items() for item in v
    #         if 'subnet' not in item and 'subnet_size' not in item]
    #
    #     try:
    #         for item in undefined_subnet:
    #             if item['id'] not in vlans_subnet.keys():
    #                 vlans_subnet[item['id']] = {
    #                     'subnet': next(subnet),
    #                     'allocation': 'auto_subnet'
    #                     }
    #             if (item['id'] in vlans_subnet.keys()
    #                     and vlans_subnet[item['id']]['allocation'] != 'auto_subnet'):
    #                 vlans_subnet[item['id']].update({
    #                     'subnet': next(subnet),
    #                     'allocation': 'auto_subnet'
    #                      })
    #     except StopIteration:
    #         raise AnsibleError('Run out of subnets.')
    #
    #     return utils.dump_datafile('vlans_subnet', vlans_subnet)
    #
    # def _host_vlans(self):
    #     mlag = self.mlag()
    #     vlans = self._vlans()
    #
    #     _host_vlans = defaultdict(dict)
    #     for host in inv.groups('border') + inv.groups('leaf'):
    #         if host in mlag.keys():
    #             bonds = mlag[host]['bonds']
    #             vids = list(set(
    #                 [x for _, v in bonds.items()
    #                  for x in utils.cluster_to_range(v['vids'])
    #                  ]))
    #             tenants = utils.unique(
    #                 [vlans[vid]['tenant'] for vid in vids])
    #
    #             for vid, value in vlans.items():
    #                 if (value['name'] == 'transport_vni'
    #                         and value['tenant'] in tenants):
    #                     vids.append(vid)
    #             for vid in vids:
    #                 _host_vlans[host].update({vid: vlans[vid]})
    #
    #         else:
    #             for vid, value in vlans.items():
    #                 if (value['name'] == 'transport_vni'
    #                         and value['tenant']):
    #                     _host_vlans[host].update({vid: value})
    #
    #     return dict(_host_vlans)
    #
    # def vxlan(self):
    #     host_vlans = self._host_vlans()
    #     base_name = 'vni'
    #     vxlan = {}
    #     for host in host_vlans:
    #         lo = self.loopbacks()[host]['ip_addresses'][0].split('/')[0]
    #         vxlan[host] = {
    #             'local_tunnelip': lo,
    #             'vxlan': {}
    #             }
    #
    #         for vid, value in host_vlans[host].items():
    #             name = "{}{}".format(base_name, vid)
    #             vxlan[host]['vxlan'][name] = {
    #                 'tenant': value['tenant'],
    #                 'id': vid,
    #                 'vlan': vid,
    #                 'type': value['type']
    #             }
    #
    #     return vxlan
    #
    # def svi(self):
    #     host_vlans = self._host_vlans()
    #     vlan_subnets = self._vlans_subnet()
    #
    #     svi = defaultdict(lambda: defaultdict(dict))
    #     for host, vids in host_vlans.items():
    #         if host in inv.groups('leaf'):
    #             host_id = self._host_id(host)
    #             rack_id = self._rack_id(host)
    #
    #             for vid, value in vids.items():
    #                 if value['type'] == 'l2':
    #                     virtual_mac = (
    #                         utils.mac_address('44:38:39:FF:01:00', vid)
    #                         )
    #                     virtual_address = (
    #                         utils.get_ip(vlan_subnets[vid]['subnet'], -2)
    #                         )
    #                     address = (
    #                         utils.get_ip(
    #                             vlan_subnets[vid]['subnet'], -(int(host_id + 2)
    #                                                            ))
    #                         )
    #                     svi[host][vid] = {
    #                         'virtual_mac': virtual_mac,
    #                         'virtual_address': virtual_address,
    #                         'address': address,
    #                         'tenant': value['tenant'],
    #                         'type': value['type']
    #                         }
    #                 if value['type'] == 'l3':
    #                     router_mac = (
    #                         utils.mac_address(
    #                             '44:39:39:FF:FF:FF', -(rack_id))
    #                             )
    #                     svi[host][vid] = {
    #                         'tenant': value['tenant'],
    #                         'router_mac': router_mac,
    #                         'type': value['type']
    #                         }
    #         else:
    #             svi[host] = vids
    #
    #     return utils.default_to_dict(svi)
    #
    # def ptp_external_networks(self):
    #     base_net_prefix = utils.load_masterfile(
    #         'base_networks')['external_connectivity']
    #     external_conn = utils.load_datafile('external_networks')
    #
    #     if external_conn['base_net_prefix'] != base_net_prefix:
    #         external_conn = (
    #             {'base_net_prefix': base_net_prefix, 'networks': {}}
    #             )
    #     get_subnet = utils.get_subnet(
    #         base_net_prefix, list(external_conn['networks'].keys()), 30)
    #     tvids = {vid: value for vid, value in self._vlans().items()
    #              if value['name'] == 'transport_vni'}
    #     e_tvids = utils.unique(
    #         [v['vid'] for _, v in external_conn['networks'].items()])
    #     e_links = (
    #         [v['links'] for _, v in external_conn['networks'].items()]
    #         )
    #
    #     _links = []
    #     for item in utils.load_masterfile('external_connectivity'):
    #         links = self._links(item, slice=True)
    #         for link in links:
    #             _link = [[link[0], link[1]], [link[2], link[3]]]
    #             _links.append(_link)
    #             for tvid in sorted(tvids.keys()):
    #                 if tvid not in e_tvids or _link not in e_links:
    #                     external_conn['networks'][next(get_subnet)] = {
    #                         'vid': tvid,
    #                         'links': _link,
    #                         'vrf': tvids[tvid]['tenant']
    #                     }
    #
    #     for k, v in external_conn['networks'].copy().items():
    #         if v['vid'] not in tvids.keys() or v['links'] not in _links:
    #             external_conn['networks'].pop(k)
    #
    #     return utils.dump_datafile('external_networks', external_conn)
    #
    # def unnumbered_interfaces(self):
    #     # Generate interfaces unnumebered base on fabric variable
    #     iface_unnum = defaultdict(list)
    #     for item in utils.load_masterfile('fabric'):
    #         links = self._links(item)
    #         for link in links:
    #             host, iface, nhost, niface = link
    #             iface_unnum[host].append({
    #                 'interface': iface,
    #                 'nhost': nhost,
    #                 'ninterface': niface,
    #                 'ngroup': inv.group_names(nhost)[0]
    #             })
    #
    #     return iface_unnum
    #
    # def ptp_ip_interfaces(self):
    #     # External connectivity point-to-point networks
    #     interfaces_ip = defaultdict(list)
    #     for k, v in self.ptp_external_networks()['networks'].items():
    #         for index, item in enumerate(v['links']):
    #             host, iface = item
    #             vif = '{}.{}'.format(iface, v['vid'])
    #             nhost = v['links'][index - 1][0]
    #             interfaces_ip[host].append({
    #                 'vrf': v['vrf'],
    #                 'interface': vif,
    #                 'address': utils.r_get_ip(k, index),
    #                 'nhost': nhost,
    #                 'ninterface': '{}.{}'.format(v['links'][index - 1][1], v['vid']),
    #                 'naddress': utils.r_get_ip(k, (index - 1)),
    #                 'ngroup': inv.group_names(nhost)[0]
    #
    #             })
    #
    #     return interfaces_ip
    #
    # def bgp_neighbors(self):
    #
    #     bgp_config = {}
    #     # BGP global config
    #     for group, asn in utils.load_masterfile('base_asn').items():
    #         for host in inv.groups(group):
    #             host_id = self._host_id(host)
    #             lo = self.loopbacks()[host]['ip_addresses'][0]
    #             router_id = lo.split('/')[0]
    #             if host in inv.groups('spine'):
    #                 _asn = asn
    #             else:
    #                 _asn = asn + host_id - 1
    #
    #             bgp_config[host] = {'as': _asn, 'router_id': router_id}
    #
    #     bgp_neighbors = defaultdict(dict)
    #     unnum_ifaces = self.unnumbered_interfaces()
    #     ptp_ifaces_ip = self.ptp_ip_interfaces()
    #
    #     for host in inv.groups():
    #         if host in unnum_ifaces:
    #             neighbors = {}
    #             for item in unnum_ifaces[host]:
    #                 neighbors[item['interface']] = {
    #                     'remote_as': 'external',
    #                     'router_id': bgp_config[item['nhost']]['router_id'],
    #                     'peer_group': item['ngroup']
    #                 }
    #                 bgp_neighbors[host]['global'] = {
    #                             'router_id': bgp_config[host]['router_id'],
    #                             'as': bgp_config[host]['as'],
    #                             'neighbors': neighbors
    #                 }
    #
    #         if host in ptp_ifaces_ip:
    #             neighbors = {}
    #             for item in ptp_ifaces_ip[host]:
    #                 neighbors[item['naddress'].split('/')[0]] = {
    #                     'remote_as': bgp_config[item['nhost']]['as'],
    #                     'router_id': bgp_config[item['nhost']]['router_id'],
    #                     'peer_group': item['ngroup']
    #                 }
    #
    #                 bgp_neighbors[host][item['vrf']] = {
    #                     'router_id': bgp_config[host]['router_id'],
    #                     'as': bgp_config[host]['as'],
    #                     'neighbor': neighbors
    #                 }
    #
    #     return bgp_neighbors
    #
    # def check_interfaces(self):
    #     ifaces = defaultdict(dict)
    #
    #     interfaces = {
    #         'external_connectivity': (
    #             utils.load_masterfile('external_connectivity')
    #             ),
    #         'fabric': utils.load_masterfile('fabric'),
    #         'mlag_bonds': utils.load_masterfile('mlag_bonds'),
    #         'mlag_peerlink_interface': (
    #             utils.load_masterfile('mlag_peerlink_interface')
    #             )
    #     }
    #
    #     ifaces = defaultdict(lambda: defaultdict(list))
    #
    #     for item in interfaces['external_connectivity']:
    #         for link in self._links(item):
    #             ifaces[link[0]]['external_connectivity'].append(link[1])
    #
    #     for item in interfaces['fabric']:
    #         for link in self._links(item):
    #             ifaces[link[0]]['fabric'].append(link[1])
    #
    #     for host in inv.groups('leaf'):
    #         rack = self._rack_id(host, id=False)
    #         ifaces[host]['mlag_bonds'] = (
    #             list(map(itemgetter('members'), interfaces['mlag_bonds'][rack])
    #                  ))
    #         ifaces[host]['mlag_peerlink_interface'] = (
    #             utils.cluster_to_range(
    #                 utils.load_masterfile('mlag_peerlink_interface')
    #                 )
    #             )
    #
    #     checkconfigvars.interfaces(ifaces)
