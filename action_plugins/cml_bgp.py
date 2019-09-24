from __future__ import (absolute_import, division)
__metaclass__ = type

import collections
import re

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

from cumulus_custom_plugins.helpers import get_run_block_config, get_diff_commands


class ActionModule(ActionBase):

    CONFIG_RE = re.compile(r'net add bgp.*')

    def _command_to_data(self, commands):
        ''' Return a structure data of net commands and a normalised running config '''

        if len(commands) == 0:
            return {'data': {}, 'commands': []}

        data = collections.defaultdict(dict)

        bgp_as = None

        for command in commands:
            m = re.match(self.CONFIG_RE, command)
            if not m:
                raise AnsibleError('regex does not include config: %s' % command)

            for command in commands:
                default_bgp = re.match('net add bgp (?!vrf).*', command)

                if default_bgp:
                    if command.startswith('net add bgp autonomous-system'):
                        bgp_as = re.search('\\d+', command).group()
                        data[bgp_as].setdefault('default', [])

                    data[bgp_as]['default'].append(command)
                    continue

                vrf_bgp = re.match('net add bgp vrf (?P<vrf>\\w+) (?P<config>.*)', command)

                if vrf_bgp:
                    vrf, config = vrf_bgp.group('vrf'), vrf_bgp.group('config')
                    data[bgp_as].setdefault(vrf, [])

                    data[bgp_as][vrf].append('net add bgp vrf %s %s' % (vrf, config))

        return {'data': data, 'commands': commands}

    def _get_commands(self, running, intent, dev_os):

        _intent = self._command_to_data(intent)
        _running = self._command_to_data(running)

        frr_changed = False
        _del = []

        if len(running) > 0:
            for asn, v in _running['data'].items():
                if asn not in _intent['data']:
                    _del.append('del bgp autonomous-system %s' % asn)
                    for vrf in v:
                        if vrf != 'default':
                            _del.append('del bgp vrf %s autonomous-system %s' % (vrf, asn))
                    frr_changed = True
                    break

                for vrf, configs in v.items():
                    if vrf not in _intent['data'][asn]:
                        _del.append('del bgp vrf %s autonomous-system %s' % (vrf, asn))
                        frr_changed = True
                        continue

                    for config in configs:
                        if config not in _intent['data'][asn][vrf]:
                            _del.append(config.replace('net add', 'del'))

        diff = get_diff_commands(_running['commands'], _intent['commands'], dev_os)

        running_commands = _running['commands'] if not frr_changed else []
        _add = [
            i.replace('net add', 'add')
            for i in _intent['commands'] if i not in running_commands
        ]

        return _del + _add, "\n".join(diff), frr_changed

    def run(self, tmp=None, task_vars=None):

        changed, failed, msg = False, False, None

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        dev_os = task_vars['ansible_network_os']
        commit = not task_vars.get('ansible_check_mode')
        running = get_run_block_config(self._task.args['running'], self.CONFIG_RE)
        intent = self._task.args['intent'].splitlines()

        if len(intent) < 1:
            raise AnsibleError('No intent configuration found')

        commands, diff, frr_changed = self._get_commands(running, intent, dev_os)

        if len(commands) > 0:

            msg = diff
            self._task.tags.append('print_action')

            if commit:
                module_args = {'template': "\n".join(commands), 'atomic': True}
                _result = self._execute_module(
                    module_name='nclu', module_args=module_args, task_vars=task_vars)

                if frr_changed:
                    _module_args = {
                        'src': '/etc/frr/frr.conf.sav',
                        'dest': '/etc/frr/frr.conf',
                        'owner': 'frr',
                        'group': 'frr',
                        'mode': 'u=rw,g=r',
                        'remote_src': 'yes',
                    }
                    self._execute_module(
                        module_name='copy', module_args=_module_args, task_vars=task_vars)

                    self._execute_module(
                        module_name='systemd',
                        module_args={'name': 'frr', 'state': 'reloaded'},
                        task_vars=task_vars
                    )

                if _result.get('failed'):
                    return _result

                changed = True

        facts = dict(commands=commands, intent=intent, running=running)
        result.update(dict(changed=changed, failed=failed, msg=msg, ansible_facts=facts))
        return result
