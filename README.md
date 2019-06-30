Note that Cumulus Linux, Vyos, Debian and Ubuntu devices only are included in configurations and tested.

### 1. Test deployment using GNS3
*The following steps require to have a knowledge on how to use GNS3*
  - #### Setup
    - Download and install [GNS3](https://www.gns3.com/software)
    - Download and import [GNS3 LAB]
    - Start `mgmt-server1, mgmt-switch1` and `edge1` machine and wait to fully boot up, after that start all the machine
    - Console to `mgmt-server01` and run the commands below to deploy devices configurations
    ```
    $ ansible-playbook configs.yml
    ```
  - #### Adding a devices to the existing topology
    In GNS3 GUI add a CumulusVX appliance. For this setup example we will add an addtiontional leaf named `leaf05` and `leaf06`.

    - Edit the inventory file named `devices` and add the the device in the correct group in this example under `leaf` group. Add the `mgmt_hwaddr` variable of the added device. The `mgmt_hwaddr` can be found by doing a right click on the device in GNS3 GUI, then Configure>Network>Base MAC.

    - Refer to the `master.yml` and we follow some of the variables needed to successfully connect the device to the existing topology.
      ```
      ---
      mlag_peerlink_interfaces: swp23-24

      network_links:
          fabric:
              links:
                - 'spine:swp1 -- leaf:swp21'
                - 'spine:swp23 -- border:swp23'
              interface_type: unnumbered
      ```
      Base on the variable above add the link below in GNS3 GUI.
      ```
      # MLAG Peerlink
      leaf5:swp23 to leaf6:swp23
      leaf5:swp24 to leaf6:swp24

      # Fabric link
      leaf5:swp21 to spine1:swp5
      leaf5:swp22 to spine2:swp5
      leaf6:swp21 to spine1:swp6
      leaf6:swp22 to spine2:swp6
      ```
      A little explaination about the `network_links` variable.
      The [script](https://github.com/rynldtbuen/cumulus-vxconfig) will automatically generate a list of individual host link base on the link format given. The link is a string that follows a format of:
      ```
      "ansible_group/ansible_hostname:starting_port -- ansible_group/ansible_hostname:starting_port"
      ```
      So in this example the script will generate a list of individual host `fabric` link of:
      ```
      "spine1:swp1 -- leaf1:swp21",
      "spine1:swp2 -- leaf2:swp21",
      "spine1:swp3 -- leaf3:swp21",
      "spine1:swp4 -- leaf4:swp21",
      "spine1:swp5 -- leaf5:swp21",
      "spine1:swp6 -- leaf6:swp21",
      "spine1:swp23 -- border1:swp23",
      "spine1:swp24 -- border2:swp23",
      "spine2:swp1 -- leaf1:swp22",
      "spine2:swp2 -- leaf2:swp22",
      "spine2:swp3 -- leaf3:swp22",
      "spine2:swp4 -- leaf4:swp22",
      "spine2:swp5 -- leaf5:swp22",
      "spine2:swp6 -- leaf6:swp22"
      "spine2:swp23 -- border1:swp24",
      "spine2:swp24 -- border2:swp24",
      ```

      The script will look for number of hosts if it found a `ansible_group` in the link format, then it automatically increament the starting port base on how many hosts has link to.

      More examples:
      ```
      # Define a group link
      # Link "spine:swp23 -- border:swp23" will generate a list of individual host links of:
      "spine1:swp23 -- border1:swp23",
      "spine1:swp24 -- border2:swp23",
      "spine2:swp23 -- border1:swp24",
      "spine2:swp24 -- border2:swp24"

      # Define a combination of group and host link
      # Link "spine:swp10 -- leaf05:swp15" will generate a list of individual host links of:
      "spine1:swp10 -- leaf5:swp15",
      "spine2:swp10 -- leaf5:swp16"

      # Define a host link
      # Link 'spine01:swp20 -- leaf06:swp20' will generate a list of individual host links of:
      "spine1:swp20 -- leaf6:swp20"
      ```

    - Run the command below to deploy the newly added hosts.
      ```
      $ ansible-playbook deploy.yml
      ```

##### Reset device configurations:
```
$ ansible-playbook configs.yml -t reset --skip-tags=always -l <hosts>
```

##### Upgrade device to latest release:
```
$ ansible-playbook configs.yml -t upgrade --skip-tags=always -l <hosts>
```
