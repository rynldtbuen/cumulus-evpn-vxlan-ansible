from __future__ import (absolute_import, division)
__metaclass__ = type

import collections
import re
from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

from cumulus_custom_plugins.helpers import (
    get_run_block_config, get_diff_commands, glob_to_uncluster, arrange_by)


class ActionModule(ActionBase):

    CONFIG_RE = re.compile(r'net add bond (?P<bond>\w+(\S+)) (?P<config>.*)')
    FAILD_MSG_RE = [
        re.compile(r'\w+ is not a physical interface on this switch'),
    ]

    def _command_to_data(self, commands):
        ''' Return a structure data of commands and a normalised running config '''

        if len(commands) == 0:
            return {'data': {}, 'commands': []}

        _commands = []
        data = collections.defaultdict(dict)

        slaves_pattern = re.compile(r'.*slaves (?P<slaves>.*)')

        for command in commands:
            m = re.match(self.CONFIG_RE, command)
            if not m:
                raise AnsibleError('regex does not include config: %s' % command)

            bond, config = m.group('bond'), m.group('config')

            if config.startswith('bond slaves'):
                bond_ = 'bond ' + bond
                s = re.search(slaves_pattern, command)
                data[bond_].setdefault('slaves', []).extend(s.group('slaves').split(','))
                data[bond_].setdefault('configs', [])

                _commands.append('net add %s %s' % (bond_, config))
                continue

            for _bond in glob_to_uncluster(bond):
                bond_ = 'bond ' + _bond
                data[bond_]['configs'].append(config)

                _commands.append('net add %s %s' % (bond_, config))

        return {'data': data, 'commands': sorted(_commands)}

    def _get_commands(self, running, intent, dev_os):
        ''' Return a list of net add/del commands based on running and intent config '''

        if len(running) < 1:
            for item in list(intent):
                if item.startswith('net add bond peerlink'):
                    intent.remove(item)

        _intent = self._command_to_data(intent)
        _running = self._command_to_data(running)

        diff = get_diff_commands(_running['commands'], _intent['commands'], dev_os)

        _del = []

        if len(running) > 0:
            for bond, v in _running['data'].items():
                if bond not in _intent['data']:
                    _del.append('del %s' % bond)
                    continue

                del_slaves = set(v['slaves']) - set(_intent['data'][bond]['slaves'])

                if len(del_slaves) > 0:
                    _del.append('del %s bond slaves %s' % (bond, ",".join(del_slaves)))

                for config in v['configs']:
                    if config not in _intent['data'][bond]['configs']:
                        _del.append('del %s %s' % (bond, config))

        intent_commands = arrange_by('bond slaves', _intent['commands'])

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

                module_msg = [i for i in _result.get('msg').splitlines() if i != '']
                for _msg in module_msg:
                    for failed_msg in self.FAILD_MSG_RE:
                        has_failed_msg = re.search(failed_msg, _msg)
                        if has_failed_msg:
                            msg = _msg
                            failed = True
                            break

                changed = True

        facts = {'commands': commands, 'intent': intent, 'running': running}
        result.update({'changed': changed, 'failed': failed, 'msg': msg, 'ansible_facts': facts})
        return result
