Ansible Playbook to automate Cumulus EVPN Symmetric Routing with MLAG Deployment

#### Quick start
- ##### Using GNS3
  ---
  - Download and install [GNS3](https://www.gns3.com/software) if you haven't. Required minumum version is 2.1.21
  - Download and import [cumulus-evpn-gns3.lab]
  - Start `mgmt-server1, mgmt-switch1` and `edge1` device and wait to fully boot up
  - Start all the remaining devices
  - Console to `mgmt-server1` and run the commands below:
    ```
    $ cd cumulus-evpn-symmetric
    $ ansible-playbook configs.yml
    ```
  - Console to 
  - Ssh to `server1` and ping `server3`
  - Optional: Connect `edge1` interface `eth3` to the internet using [NAT node](https://docs.gns3.com/1eMqJLSBFgcHaOGctAoNKfN1QpxdJvVsfVfPt6lVCmek/index.html#h.is6jtbk9wuyy) to verify servers can reach the internet


Device system requirements:
  - Cumulus VX 3.7.5
  - Vyos 1.1.8
  - Ubuntu 16.04
