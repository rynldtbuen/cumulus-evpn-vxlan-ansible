from __future__ import (absolute_import, division)
__metaclass__ = type

import re
from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

from cumulus_custom_plugins.helpers import get_run_block_config, get_diff_commands


class ActionModule(ActionBase):

    CONFIG_RE = re.compile(r'set interfaces loopback.*')

    def _get_commands(self, running, intent):

        for item in intent:
            m = re.match(self.CONFIG_RE, item)
            if not m:
                raise AnsibleError('regex does not include config: %s' % item)

        _del = [i.replace('set', 'delete') for i in running if i not in intent]
        _add = [i for i in intent if i not in running]

        return _del + _add

    def run(self, tmp=None, task_vars=None):

        changed, failed, msg = False, False, None

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        dev_os = task_vars['ansible_network_os']
        commit = not task_vars.get('ansible_check_mode')
        running = get_run_block_config(self._task.args['running'], self.CONFIG_RE)
        intent = sorted(self._task.args['intent'].splitlines())

        if len(intent) < 1:
            raise AnsibleError('No intent configuration found')

        diff = "\n".join(get_diff_commands(running, intent, dev_os))
        commands = self._get_commands(running, intent)

        if len(commands) > 0:

            msg = diff
            self._task.tags.append('print_action')

            if commit:
                module_args = {
                    'config': "\n".join(commands),
                    'commit_comment': 'configured by Ansible custom action plugins'
                }
                _result = self._execute_module(
                    module_name='cli_config', module_args=module_args, task_vars=task_vars)

                if _result.get('failed'):
                    return _result

                self._execute_module(
                    module_name='vyos_command',
                    module_args=dict(commands=['configure', 'save', 'exit']), task_vars=task_vars)

                changed = True

        facts = dict(commands=commands, intent=intent, running=running)
        result.update(dict(changed=changed, failed=failed, msg=msg, ansible_facts=facts))
        return result
