from cl_vx_config.configvars import ConfigVars
from cl_vx_config.utils.filters import Filters

filter = Filters()


class FilterModule:

    def filters(self):
        return {
            'get_config': self.get_config,
            'duplicate_items': self.duplicate_items
        }

    def get_config(self, v):
        configvars = ConfigVars()
        method = getattr(configvars, v)
        return method()

    def duplicate_items(self, v):
        return [item for item in set(v) if v.count(item) > 1]
