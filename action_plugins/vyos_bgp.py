from __future__ import (absolute_import, division)
__metaclass__ = type

import collections
import re

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

from cumulus_custom_plugins.helpers import get_run_block_config, get_diff_commands


class ActionModule(ActionBase):

    CONFIG_RE = re.compile(
        r'set protocols (?P<bgp>bgp \d+) (?P<config>neighbor \S+|\S+)(?P<sconfig>.*)')

    def _command_to_data(self, commands):
        ''' Return a structure data of net commands and a normalised running config '''

        if len(commands) == 0:
            return {'data': {}, 'commands': []}

        data = collections.defaultdict(dict)

        for command in commands:
            m = re.match(self.CONFIG_RE, command)
            if not m:
                raise AnsibleError('regex does not include config: %s' % command)

            bgp, config, sconfig = m.group('bgp'), m.group('config'), m.group('sconfig').strip()

            data[bgp].setdefault(config, [])

            if sconfig != '':
                data[bgp][config].append(sconfig)

        return {'data': data, 'commands': sorted(commands)}

    def _get_commands(self, running, intent, dev_os):

        _intent = self._command_to_data(intent)
        _running = self._command_to_data(running)

        diff = get_diff_commands(_running['commands'], _intent['commands'], dev_os)

        _del = []

        if len(running) > 0:
            for asn, _config in _running['data'].items():
                if asn not in _intent['data']:
                    _del.append('delete protocols %s' % asn)
                    break

                for config, sub_configs in _config.items():
                    if config not in _intent['data'][asn]:
                        _del.append('delete protocols %s %s' % (asn, config))
                        continue

                    for sub in sub_configs:
                        if sub not in _intent['data'][asn][config]:
                            _del.append('delete protocols %s %s %s' (asn, config, sub))

        _add = [i for i in _intent['commands'] if i not in _running['commands']]

        return _del + _add, "\n".join(diff)

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
                module_args = dict(
                    config="\n".join(commands),
                    commit_comment='configured by Ansible custom action plugins')
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
