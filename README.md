## Ansible Playbook to deploy Cumulus VXLAN EVPN in Symmetric Routing

### 1. Test deployment using GNS3
  - #### 1.1 Setup
    - Download and install [GNS3](https://www.gns3.com/software)
    - Download the import [GNS3 LAB]
    - Start `ansible-controller` and `mgmt01` machine and wait to fully boot up after that start all the machine
    - Console to `ansible-controller` and run the commands below
    ```
    ansible-playbook deploy
    ```
  - #### Adding more device
    - If you wish to add


### 2. Test deployment from scratch

- Follow the instructions in [ansible-configvars](https://github.com/rynldtbuen/ansible-configvars.git). Make sure you got it working before you proceed.
- Clone the playbook.
```
git clone https://github.com/rynldtbuen/cumulus-vxlan-evpn-ansible.git
```
- Enter command below and follow intructions'.
```
napalm-ansible
```
- Edit Ansible inventory named 'devices' and enter the device hardware address of the interface connected to the oob management network. This will allow the device to get the IP address and set the hostname provided by the DHCP.
```
# Example
[leaf]
leaf01 mgmt_hwaddr='0c:d9:c8:47:bf:00'
```
- Update the dnsmasq.conf
```
ansible-playbook dnsmasq.yml
```
-
- Edit the 'master.yml' base on your deployment topology.
```
# Example
network_links:
  - name: fabric
    links:
      - 'spine:swp1 -- leaf:swp21'
      - 'spine:swp23 -- border:swp23'
    interface_type: unnumbered
```
