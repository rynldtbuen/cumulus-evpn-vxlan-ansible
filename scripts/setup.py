from setuptools import setup

setup(
    name='cl_vx_config',
    version='1.0.10',
    description='Generate Ansible variables to Deploy Cumulus VXLAN-EVPN',
    author='Reynold Tabuena',
    author_email='rynldtbuen@gmail.com',
    license='MIT',
    packages=['cl_vx_config'],
    install_requires=[
        'ansible',
        'napalm',
        'ipaddress',
        'napalm-ansible',
        ],
    zip_safe=False)
