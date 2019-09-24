from __future__ import (absolute_import, division)
__metaclass__ = type

import re
from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

from cumulus_custom_plugins.helpers import get_run_block_config, get_diff_commands


class ActionModule(ActionBase):

    CONFIG_RE = re.compile(r'net add (interface|bond) peerlink.(\d+|bond).*')
    FAILD_MSG = [
        re.compile(r'\w+ is not a physical interface on this switch'),
    ]

    def _get_commands(self, running, intent, dev_os):
        ''' Return a list of net add/del commands based on running and intent config '''

        if len(running) > 0:
            running.pop(0)
            intent.pop(0)

        diff = get_diff_commands(running, intent, dev_os)

        for item in intent:
            m = re.match(self.CONFIG_RE, item)
            if not m:
                raise AnsibleError('regex does not include config: %s' % item)

        _add = [i.replace('net add', 'add') for i in intent if i not in running]

        return _add, "\n".join(diff)

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
