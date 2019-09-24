from __future__ import (absolute_import, division)
__metaclass__ = type

from ansible.plugins.action import ActionBase
from cumulus_custom_plugins.hosts import HostsConf

hostsconf = HostsConf()


class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        facts = {}
        vars = [i.strip() for i in self._task.args['vars'].split(',')]
        host = task_vars.get('inventory_hostname')
        for config in vars:
            facts[config] = hostsconf.get(config, host)

        result['changed'] = False
        result['ansible_facts'] = facts
        return result
