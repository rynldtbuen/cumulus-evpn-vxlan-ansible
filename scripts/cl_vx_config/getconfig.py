import collections
import copy
import itertools

# from ansible.errors import AnsibleError
from cl_vx_config.utils.checkconfig import CheckVars
from cl_vx_config.utils.filters import Filters
from cl_vx_config.utils import File, Inventory, Host, MACAddr, Network

filter = Filters()
inventory = Inventory()


class GetConfig:

    def __init__(self):
        pass

    def loopbacks(self):
        base_networks = CheckVars().base_networks

        lo, clag = base_networks['loopbacks'], base_networks['vxlan_anycast']
        clag_net = Network(clag)

        loopbacks = {}
        for group, subnet in lo.items():
            lo_net = Network(subnet)
            for host in inventory.hosts(group):
                _host = Host(host)
                loopbacks[host] = {
                    'ip_addresses': [], 'clag_vxlan_anycast_ip': None
                }

                lo_ip = lo_net.get_ip(_host.id, lo=True)
                loopbacks[host]['ip_addresses'].append(lo_ip)

                if _host in inventory.hosts('leaf'):
                    loopbacks[host]['clag_vxlan_anycast_ip'] = (
                        clag_net.get_ip(_host.rack_id, addr=True)
                    )

        return loopbacks

    def _vlans(self, key=None):
        master_vlans = CheckVars().vlans

        def _l3vni():

            l3vni = File('l3vni')

            ids = [v['id'] for k, v in l3vni.data.items()]
            available_vnis = iter([
                r for r in range(4000, 4091) if str(r) not in ids
            ])

            for tenant in master_vlans.keys():
                if tenant not in l3vni.data.keys():
                    vni = next(available_vnis)
                    vlan = 'vlan' + str(vni)
                    l3vni.data[tenant] = {
                        'id': str(vni), 'name': 'l3vni',
                        'type': 'l3', 'vlan': vlan
                    }

            for tenant in l3vni.data.copy().keys():
                if tenant not in master_vlans.keys():
                    del l3vni.data[tenant]

            return l3vni.dump()

        if key is not None:
            groupby_vlans = {}
            for tenant, vlans in copy.deepcopy(master_vlans).items():
                vlans.append(_l3vni()[tenant])
                for vlan in vlans:
                    vlan.update({'tenant': tenant, 'type': 'l2',
                                 'vlan': 'vlan' + vlan['id']})
                for k, v in itertools.groupby(vlans, lambda x: x[key]):
                    for item in v:
                        groupby_vlans[k] = item

            return groupby_vlans

        return master_vlans

    def dummy(self):
        return self._vlans(key='vlan')
    # def _get_l3vni(self, _tenant):
    #     for tenant, vlans in self._vlans().items():
    #         for v in vlans.items():
    #             if tenant == _tenant and v['type'] == 'l3':
    #                 return v['id']

    def mlag_peerlink(self):
        interfaces = CheckVars().mlag_peerlink_interfaces
        lo = self.loopbacks()

        mlag_peerlink = {}
        for host in inventory.hosts('leaf'):
            _host = Host(host)
            backup_ip = lo[_host.peer_host]['ip_addresses'][0].split('/')[0]
            system_mac = MACAddr('44:38:39:FF:01:00') - _host.rack_id

            if _host.id % 2 == 0:
                clag_role = '2000'
                ip, peer_ip = '169.254.1.2/30', '169.254.1.1'
            else:
                clag_role = '1000'
                ip, peer_ip = '169.254.1.1/30', '169.254.1.2'

            mlag_peerlink[host] = {
                'priority': clag_role,
                'system_mac': system_mac,
                'interfaces': interfaces,
                'backup_ip': backup_ip,
                'peer_ip': peer_ip, 'ip': ip
            }

        return mlag_peerlink

    def mlag_bonds(self):
        mlag_bonds = CheckVars().mlag_bonds

        def _clag_interfaces():

            clag_ifaces = File('clag_interfaces')

            for rack, bonds in mlag_bonds.items():
                try:
                    existing_ids = list(clag_ifaces.data[rack].values())
                except KeyError:
                    existing_ids = [0]
                    clag_ifaces.data[rack] = {}

                available_ids = iter(
                    [r for r in range(1, 200) if r not in existing_ids]
                )

                for index, bond in enumerate(bonds, start=1):
                    if bond['name'] not in clag_ifaces.data[rack].keys():
                        clag_ifaces.data[rack][bond['name']] = (
                            next(available_ids)
                        )

            for rack, bonds in clag_ifaces.data.copy().items():
                if rack in mlag_bonds.keys():
                    for bond, _ in bonds.copy().items():
                        if bond not in [v['name'] for v in mlag_bonds[rack]]:
                            del clag_ifaces.data[rack][bond]
                else:
                    del clag_ifaces.data[rack]

            return clag_ifaces.dump()

        clag_id = _clag_interfaces()
        master_vlans = self._vlans(key='id')

        rack_bonds = {}
        for rack, bonds in mlag_bonds.items():
            _bonds = []
            for bond in bonds:
                vids = filter.cluster(bond['vids'], _list=True)
                for vid in vids:
                    tenant = master_vlans[vid]['tenant']
                    break

                _bonds.append({
                    'name': bond['name'],
                    'vids': ','.join(vids),
                    'clag_id': clag_id[rack][bond['name']],
                    'tenant': tenant,
                    'members': ','.join(
                        filter.cluster(bond['members'], _list=True)),
                    'mode': 'trunk' if len(vids) > 1 else 'access',
                    'alias': '{}, {}'.format(
                        tenant, filter.cluster(bond['vids'])
                    )
                })

            rack_bonds[rack] = _bonds

        host_bonds = {}
        for rack, bonds in rack_bonds.items():
            for host in Inventory().hosts('leaf'):
                _host = Host(host)
                if _host.rack == rack:
                    host_bonds[host] = bonds

        return host_bonds

    def _host_vlans(self):
        master_vlans = self._vlans(key='id')
        host_bonds = self.mlag_bonds()

        host_vlans = {}
        for host, bonds in host_bonds.items():
            _vlans = []
            set_vids = set([])
            for bond in bonds:
                for vid in bond['vids'].split(','):
                    set_vids.add(vid)
                for id, item in master_vlans.items():
                    if (item['tenant'] == bond['tenant']
                            and item['type'] == 'l3'):
                        set_vids.add(id)
            for _vid in set_vids:
                _vlans.append(master_vlans[_vid])
            host_vlans[host] = _vlans

        return host_vlans

    def vxlan(self):
        base_name = 'vni'

        vxlan = {}
        for host, vlan in self._host_vlans().items():
            lo = self.loopbacks()[host]['ip_addresses'][0].split('/')[0]
            vxlan[host] = {
                'local_tunnelip': lo,
                'vxlan': []
            }

            for v in vlan:
                vxlan[host]['vxlan'].append({
                    'name': base_name + v['id'],
                    'tenant': v['tenant'],
                    'id': v['id'],
                    'vlan': 'vlan' + v['id'],
                    'type': v['type']
                })

        return vxlan

    def _vlans_network(self):
        master_vlans = self._vlans()
        vlans_network = File('vlans_network')
        _vlans = self._vlans(key='id')

        # Delete VLANs networknot in master fileq
        for vlan, v in vlans_network.data.copy().items():
            if v['id'] not in _vlans.keys():
                vlans_network.data.pop(vlan)

        existing_net_prefix = list(
            map(lambda x: x['network_prefix'], vlans_network.data.values())
        )

        checkvars = CheckVars()
        base_vlans_network = Network(checkvars.base_networks['vlans'])
        for tenant, vlans in master_vlans.items():
            for vlan in vlans:
                _vlan = _vlans[vlan['id']]
                key = _vlan['vlan']
                if 'network_prefix' in vlan:
                    _vlan['allocation'] = 'manual'
                    if key not in vlans_network.data.keys():
                        checkvars.vlans_network(
                            tenant, vlan, vlans_network.data
                        )
                        vlans_network.data[key] = _vlan
                    else:
                        if (vlans_network.data[key]['network_prefix']
                                != vlan['network_prefix']):
                            checkvars.vlans_network(
                                tenant, vlan, vlans_network.data
                            )
                            vlans_network.data[key].update({
                                'network_prefix': vlan['network_prefix'],
                                'allocation': 'manual'
                            })

                elif 'prefixlen' in vlan:
                    _vlan['allocation'] = 'auto_prefixlen'
                    if key not in vlans_network.data.keys():
                        subnet = base_vlans_network.get_subnet(
                            existing_net_prefix, prefixlen=vlan['prefixlen']
                        )
                        _vlan['network_prefix'] = subnet
                        vlans_network.data[key] = _vlan

                    else:
                        if (vlans_network.data[key]['allocation']
                                != 'auto_prefixlen'):
                            subnet = base_vlans_network.get_subnet(
                                existing_net_prefix,
                                prefixlen=vlan['prefixlen']
                            )
                            vlans_network.data[key].update({
                                'network_prefix': subnet,
                                'allocation': 'auto_prefixlen'
                            })
                else:
                    _vlan['allocation'] = 'auto_network_prefix'
                    if key not in vlans_network.data.keys():
                        subnet = base_vlans_network.get_subnet(
                            existing_net_prefix
                        )
                        _vlan['network_prefix'] = subnet
                        vlans_network.data[key] = _vlan
                    else:
                        if (vlans_network.data[key]['allocation']
                                != 'auto_network_prefix'):
                            subnet = base_vlans_network.get_subnet(
                                existing_net_prefix
                            )
                            vlans_network.data[key].update({
                                'network_prefix': subnet,
                                'allocation': 'auto_network_prefix'
                            })

        return vlans_network.dump()

    def vlan_interface(self):
        vlans_network = self._vlans_network()
