from __future__ import (absolute_import, division)
__metaclass__ = type

import collections
import re

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

from cumulus_custom_plugins.helpers import get_run_block_config, get_diff_commands


class ActionModule(ActionBase):

    CONFIG_RE = re.compile(r'net add vrf (?!mgmt)\S+.*')

    def _command_to_data(self, commands):
        ''' Return a structure data of net commands and a normalised running config '''

        if len(commands) == 0:
            return {'data': {}, 'commands': []}

        data = collections.defaultdict(list)

        for command in commands:
            m = re.match(self.CONFIG_RE, command)
            if not m:
                raise AnsibleError('regex does not include config: %s' % command)

        return {'data': data, 'commands': sorted(commands)}

    def _get_commands(self, running, intent, dev_os):

        _intent = self._command_to_data(intent)
        _running = self._command_to_data(running)

        diff = get_diff_commands(_running['commands'], _intent['commands'], dev_os)

        _del = [
            i.replace('net add', 'del')
            for i in _running['commands'] if i not in _intent['commands']
        ]

        _add = [
            i.replace('net add', 'add')
            for i in _intent['commands'] if i not in _running['commands']
        ]

        return _add + _del, "\n".join(diff)

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

        commands, diff = self._get_commands(running, intent, dev_os)

        if len(commands) > 0:

            msg = diff
            self._task.tags.append('print_action')

            if commit:
                module_args = {'template': "\n".join(commands), 'atomic': True}
                _result = self._execute_module(
                    module_name='nclu', module_args=module_args, task_vars=task_vars)

                # if frr_changed:
                #     _module_args = {
                #         'src': '/etc/frr/frr.conf.sav',
                #         'dest': 'etc/frr/frr.conf',
                #         'owner': 'frr',
                #         'group': 'frr',
                #         'mode': 'u=rw,g=r',
                #         'remote_src': 'yes',
                #     }
                #     self._execute_module(
                #         module_name='copy', module_args=_module_args, task_vars=task_vars)
                #
                #     self._execute_module(
                #         module_name='systemd',
                #         module_args={'name': 'frr', 'state': 'reloaded'},
                #         task_vars=task_vars
                #     )

                if _result.get('failed'):
                    return _result

                changed = True

        facts = dict(commands=commands, intent=intent, running=running)
        result.update(dict(changed=changed, failed=failed, msg=msg, ansible_facts=facts))
        return result
