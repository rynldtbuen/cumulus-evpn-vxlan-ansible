#### Ansible Playbook to deploy Cumulus VXLAN EVPN in Symmetric Routing

### 1. Test deployment using GNS3
- Download and install [GNS3](https://www.gns3.com/software)
- Download the import [GNS3 LAB]

### 1. Test deployment from scratch
** Note that it is recommended to create a Python Virtual Environment and run everything from there unless you have a machine intended for this. **

  111.1 Install prerequisite

```
# Python3.5 and above is required
sudo apt-get install python3-pip git
```

```
# Create a directory and a virtual environment
mkdir venv
pip3 install virtualenv
# Make sure python3 is use in creating the virtualenv
virtualenv --python=python3.5 venv
source venv/bin/activate
```
#### 2. Clone and Install
Below is a python script use as a Ansible custom filter and required to simplify the configuration variables define in 'master.yml' file in the playbook.

```
git clone https://github.com/rynldtbuen/vxlan-evpn-configvars.git
cd vxlan-evpn-configvars
pip install -e .
```
Clone the Ansible playbook.
```
git clone https://github.com/rynldtbuen/cumulus-vxlan-evpn-ansible.git
cd cumulus-vxlan-evpn-ansible
```
The playbook also require the NAPALM module. Copy the below command output to 'ansible.cfg'.
```
napalm-ansible
```
#### 3. Using the Ansible Playbook
- Edit the Ansible inventory file named 'devices' and change accordingly. It is recommended to leave out follow device naming format (ex. leaf01, spine01, leaf01)
