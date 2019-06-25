### 1. Test deployment using GNS3
*Note that the following steps require to have a knowledge on how to use GNS3*
  - #### Setup
    - Download and install [GNS3](https://www.gns3.com/software)
    - Download and import [GNS3 LAB]
    - Start `mgmt-server01, mgmt-switch01` and `edge01` machine and wait to fully boot up, after that start all the machine
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
      leaf05:swp23 to leaf06:swp23
      leaf05:swp24 to leaf06:swp24

      # Fabric link
      leaf05:swp21 to spine01:swp5
      leaf05:swp22 to spine02:swp5
      leaf06:swp21 to spine01:swp6
      leaf06:swp22 to spine02:swp6
      ```
      A little explaination about the `network_links` variable.
      The [script](https://github.com/rynldtbuen/cumulus-vxconfig) will automatically generate a list of individual host link base on the link format given. The link is a string that follow a format of:
      ```
      "ansible_group/ansible_hostname:starting_port -- ansible_group/ansible_hostname:starting_port"
      ```
      So in this example the script will generate a list of individual host `fabric` link of:
      ```
      "spine01:swp1 -- leaf01:swp21",
      "spine01:swp2 -- leaf02:swp21",
      "spine01:swp3 -- leaf03:swp21",
      "spine01:swp4 -- leaf04:swp21",
      "spine01:swp5 -- leaf05:swp21",
      "spine01:swp6 -- leaf06:swp21",
      "spine01:swp23 -- border01:swp23",
      "spine01:swp24 -- border02:swp23",
      "spine02:swp1 -- leaf01:swp22",
      "spine02:swp2 -- leaf02:swp22",
      "spine02:swp3 -- leaf03:swp22",
      "spine02:swp4 -- leaf04:swp22",
      "spine02:swp5 -- leaf05:swp22",
      "spine02:swp6 -- leaf06:swp22"
      "spine02:swp23 -- border01:swp24",
      "spine02:swp24 -- border02:swp24",
      ```
      The script will look for number of hosts if it found a `ansible_group` in the link format, then it automatically increament the starting port base on how many hosts has link to.

      More examples:
      ```
      # Define a group link
      # Link "spine:swp23 -- border:swp23" will generate a list of individual host links of:
      "spine01:swp23 -- border01:swp23",
      "spine01:swp24 -- border02:swp23",
      "spine02:swp23 -- border01:swp24",
      "spine02:swp24 -- border02:swp24"

      # Define a combination of group and host link
      # Link "spine:swp10 -- leaf05:swp15" will generate a list of individual host links of:
      "spine01:swp10 -- leaf05:swp15",
      "spine02:swp10 -- leaf05:swp16"

      # Define a host link
      # Link 'spine01:swp20 -- leaf06:swp20' will generate a list of individual host links of:
      "spine01:swp20 -- leaf06:swp20"
      ```

    - Run the command below to update the `dnsmasq.conf` and follow the instructions at the end of playbook run.
      ```
      $ ansible-playbook deploy.yml
      ```
