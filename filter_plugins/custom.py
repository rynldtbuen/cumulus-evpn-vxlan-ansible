from cumulus_vxconfig.configvars import ConfigVars
from cumulus_vxconfig.utils.filters import Filters

f = Filters()


class FilterModule:

    def filters(self):
        return {
            'get_config': self.get_config,
            'duplicate_items': self.duplicate_items,
            'uncluster': self.uncluster,
            'cluster': self.cluster,
            'warning': self.warning
        }

    def get_config(self, v):
        configvars = ConfigVars()
        method = getattr(configvars, v)
        return method()

    def uncluster(self, v):
        return f.uncluster(v)

    def cluster(self, v):
        return f.cluster(v)

    def duplicate_items(self, v):
        return [item for item in set(v) if v.count(item) > 1]

    def warning(self, txt):
        print(
            "\033[1;35mWARNING: {}".format(txt)
        )
