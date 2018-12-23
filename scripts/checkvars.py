#!/usr/bin/python
from ipaddress import IPv4Network
from itertools import combinations
import utilities
import json

utils = utilities.Utilities()


class CheckVars:

    def vlans(self):

        mf_vlans = utils.load_masterfile('vlans')
        df_vlans = utils.load_datafile('vlans')

        vids = [vlan['id'] for tenant in mf_vlans for vlan in mf_vlans[tenant]]
        duplicate_vids = utils.duplicate_items(vids)
        if len(duplicate_vids) > 0:
            try:
                vid = duplicate_vids[0]
                m = "VLAN{} was already assigned to tenant \"{}\"."
                raise Exception(m.format(vid, df_vlans[vid]['tenant']))
            except KeyError:
                m = "VLAN{} was found duplicate."
                raise Exception(m.format(vid))

    # def clag(self, clag_peerlink_interface):
    #
    #     peerlink_interface = utils.cluster_to_range(
    #         clag_peerlink_interface)
    #     duplicate_peerlink_interface = utils.duplicate_items(
    #         peerlink_interface)
    #     if len(duplicate_peerlink_interface) > 0:
    #         m = "ClAG peerlink interface \"{}\" was already assigned."
    #         raise Exception(m.format(duplicate_peerlink_interface[0]))

    def mlag_bonds(self, vlans, mlag_bonds):

        for rack, value in mlag_bonds.items():

            vids = utils.unique(
                utils.cluster_to_range([item['vids'] for item in value]))
            for vid in vids:
                if vid not in vlans.keys():
                    m = "VLAN{}({}) does not exist in list of VLANS."
                    raise Exception(m.format(vid, rack))

            for bond in value:
                vids = utils.unique(utils.cluster_to_range(bond['vids']))
                bond_tenant = utils.unique(
                    [vlans[vid]['tenant'] for vid in vids])
                if len(bond_tenant) > 1:
                    m = "Bond '{}' assigned vids belongs to multiple tenants."
                    raise Exception(
                        m.format(bond['name']))

            bond_members = utils.cluster_to_range(
                [item['members'] for item in value])
            dup_member = utils.duplicate_items(bond_members)
            if len(dup_member) > 0:
                m = "Port '{}'({}) was already assigned or has a duplicate entry."
                raise Exception(m.format(dup_member[0], rack))

            bonds = [item['name'] for item in value]
            dup_bonds = utils.duplicate_items(bonds)
            if len(dup_bonds) > 0:
                m = ("Bond '{}'({}) was already "
                     "assigned or has a duplicate entry.")
                raise Exception(m.format(dup_bonds[0], rack))

    def vlan_subnets(self, new_subnets, existing_subnets, vlans):

        def _get_vid(subnet, lookup):
            if lookup == 'vlans':
                for tenant, value in utils.load_masterfile('vlans').items():
                    for item in value:
                        if 'subnet' in item and item['subnet'] == subnet:
                            return "(VLAN{}, {})".format(item['id'], tenant)
            else:
                for vid, value in existing_subnets.items():
                    if value['subnet'] == subnet:
                        return "(VLAN{}, {})".format(vid, vlans[vid]['tenant'])

        _new_subnets = []
        for subnet in new_subnets:
            try:
                _new_subnets.append(IPv4Network(subnet))
            except ValueError:
                m = ("Invalid network: {}{}, it is an "
                     "IP address that belong to {} network.")
                raise Exception(
                    m.format(
                        subnet, _get_vid(subnet, 'vlans'), IPv4Network(
                            subnet, strict=False)))

        x_subnets = combinations(_new_subnets, 2)
        for subnet in x_subnets:
            if subnet[0] == subnet[1]:
                m = ("Duplicate subnet: {}. "
                     "Check your 'vlans' variable in 'master.yml'")
                raise Exception(m.format(subnet[0]))

            if subnet[0].overlaps(subnet[1]):
                m = ("Subnets {}{} overlaps with subnet {}{}. "
                     "Check your 'vlans' variable in 'master.yml'")
                value0 = _get_vid(str(subnet[0]), 'vlans')
                value1 = _get_vid(str(subnet[1]), 'vlans')
                raise Exception(
                    m.format(subnet[0], value0,
                             subnet[1], value1))

        _existing_subnets = [IPv4Network(es['subnet'])
                             for _, es in existing_subnets.items()]
        y_subnets = [(ns, es)
                     for ns in _new_subnets for es in _existing_subnets]
        for subnet in y_subnets:
            if subnet[0] == subnet[1]:
                m = "Subnet {}{} was already assigned to {}"
                value0 = _get_vid(str(subnet[0]), 'vlans')
                value1 = _get_vid(str(subnet[1]), 'existing_subnets')
                raise Exception(m.format(subnet[0], value0, value1))

            if subnet[0].overlaps(subnet[1]):
                m = ("Subnet {}{} overlaps with existing subnet {}{}. "
                     "Check your 'vlans' variable in 'master.yml'")
                value0 = _get_vid(str(subnet[0]), 'vlans')
                value1 = _get_vid(str(subnet[1]), 'existing_subnets')
                raise Exception(m.format(subnet[0], value0,
                                         subnet[1], value1))

    def links(self, links):
        for group, value in links.items():
            try:
                iface = [y for x in utils.map_attr(
                    'iface_range', value) for y in x]
            except KeyError:
                iface = [x for x in utils.map_attr(
                    'iface', value)]
            dup_iface = utils.duplicate_items(iface)
            if len(dup_iface) > 0:
                in_item = [item['in_item']
                           for item in value if dup_iface[0] == item['iface']]

                m = ("Overlapping fabric interface: '{}' "
                     "in '{}' group. Check you 'fabric' variable in "
                     "'master.yml'\n{}")
                raise Exception(m.format(
                    dup_iface[0], group, json.dumps({'errors': in_item}, indent=2)
                    ))
