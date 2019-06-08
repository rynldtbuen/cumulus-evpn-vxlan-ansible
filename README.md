## Ansible Playbook to deploy Cumulus VXLAN EVPN in Symmetric Routing

### 1. Test deployment using GNS3
  - #### Setup
    - Download and install [GNS3](https://www.gns3.com/software)
    - Download the import [GNS3 LAB]
    - Start `ansible-controller` and `mgmt01` machine and wait to fully boot up after that start all the machine
    - Console to `ansible-controller` and run the commands below to deploy device configurations
    ```
    $ ansible-playbook deploy
    ```
  - #### Adding a device to the existing topology
    - In GNS3 GUI add the device and link below.
    ```
    # Fabric link
    leaf05:swp21 to spine01:swp5
    leaf05:swp22 to spine02:swp5
    leaf06:swp21 to spine01:swp6
    leaf06:swp22 to spine02:swp6
    # Mlag peerlink
    leaf05:swp23 to leaf06:swp23
    leaf05:swp24 to leaf06:swp24
    ```
    - Edit the inventory file named `devices` and add the name and `mgmt_hwaddr` of the added device. The `mgmt_hwaddr` can be found by doing a right click to the device, then Configure>Network>Base MAC.
    - Run the command below to update and `dnsmasq.conf`.
    ```
    $ ansible-playbook dnsmasq.yml
    ```
    - Start the device and run the command below to deploy the ssh-key to the newly added device.
    ```
    $ ansible-playbook ssh-key
    ```
    - Run the command below to deploy the rest of the configuration
    ```
    $ ansible-playbook deploy
    ```
