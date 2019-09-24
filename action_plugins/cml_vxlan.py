from __future__ import (absolute_import, division)
__metaclass__ = type

import collections
import re
from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

from cumulus_custom_plugins.helpers import (
    get_run_block_config, get_diff_commands, glob_to_uncluster, arrange_by)


class ActionModule(ActionBase):

    CONFIG_RE = re.compile(r'net add vxlan (?P<vxlan>\w+\S+) (?P<config>.*)')

    def _command_to_data(self, commands):
        ''' Return a structure data of net_commands and a normalised running config '''

        if len(commands) == 0:
            return {'data': {}, 'commands': []}

        _commands = []
        data = collections.defaultdict(list)

        for command in commands:
            m = re.match(self.CONFIG_RE, command)
            if not m:
                raise AnsibleError('regex does not include config: %s' % command)

            vxlan, config = m.group('vxlan'), m.group('config')

            for _vxlan in glob_to_uncluster(vxlan):
                vxlan_ = 'vxlan ' + _vxlan
                data[vxlan_].append(config)

                _commands.append('net add %s %s' % (vxlan_, config))

        return {'data': data, 'commands': sorted(_commands)}

    def _get_commands(self, running, intent, dev_os):
        ''' Return a list of net add/del commands based on running and intent config '''

        _intent = self._command_to_data(intent)
        _running = self._command_to_data(running)

        diff = get_diff_commands(_running['commands'], _intent['commands'], dev_os)

        _del = []

        if len(running) > 0:
            for vxlan, configs in _running['data'].items():
                if vxlan not in _intent['data']:
                    _del.append('del %s' % vxlan)
                    continue

                for config in configs:
                    if config not in _intent['data'][vxlan]:
                        _del.append('del %s %s' % (vxlan, config))

        intent_commands = arrange_by('vxlan id', _intent['commands'])

        _add = [
            i.replace('net add', 'add')
            for i in intent_commands if i not in _running['commands']
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

                if _result.get('failed'):
                    return _result

                changed = True

        facts = {'commands': commands, 'intent': intent, 'running': running}
        result.update({'changed': changed, 'failed': failed, 'msg': msg, 'ansible_facts': facts})
        return result
