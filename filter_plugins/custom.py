from cl_vx_config.configvars import ConfigVars
from cl_vx_config.utils.filters import Filters

filter = Filters()


class FilterModule:

    def filters(self):
        return {
            'get_config': self.get_config
        }

    def get_config(self, v):
        configvars = ConfigVars()
        method = getattr(configvars, v)
        return method()
