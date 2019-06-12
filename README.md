### 1. Test deployment using GNS3
*Note that the following steps require to have a knowledge on how to use GNS3*
  - #### Setup
    - Download and install [GNS3](https://www.gns3.com/software)
    - Download the import [GNS3 LAB]
    - Start `mgmt-server01, mgmt-switch01` and `edge01` machine and wait to fully boot up, after that start all the machine
    - Console to `mgmt-server01` and run the commands below to deploy devices configurations
    ```
    $ ansible-playbook deploy.yml
    ```
  - #### Adding a devices to the existing topology
    - In GNS3 GUI add CumulusVX switch, rename the switch correspond to name below and add the link.
    ```
    # Fabric link
    leaf05:swp21 to spine01:swp5
    leaf05:swp22 to spine02:swp5
    leaf06:swp21 to spine01:swp6
    leaf06:swp22 to spine02:swp6
    # MLAG Peerlink
    leaf05:swp23 to leaf06:swp23
    leaf05:swp24 to leaf06:swp24
    ```
    - Edit the inventory file named `devices` and add the the device in the correct group in this example under `leaf` group. Add the `mgmt_hwaddr` variable of the added device. The `mgmt_hwaddr` can be found by doing a right click on the device, then Configure>Network>Base MAC.
    - Run the command below to update the `dnsmasq.conf` and follow the instructions at the end of playbook run.
    ```
    $ ansible-playbook dnsmasq.yml
    ```
