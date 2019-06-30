from cumulus_vxconfig.configvars import ConfigVars
from cumulus_vxconfig.utils.filters import Filters


class FilterModule:

    configvars = ConfigVars()
    filter = Filters()

    def filters(self):
        return {
            'get_config': self.get_config,
            'duplicate_items': self.duplicate_items,
            'uncluster': self.uncluster,
            'cluster': self.cluster,
            'warning': self.warning
        }

    def get_config(self, v):
        method = getattr(self.configvars, v)
        return method()

    def uncluster(self, v):
        return self.filter.uncluster(v)

    def cluster(self, v):
        return self.filter.cluster(v)

    def duplicate_items(self, v):
        return [item for item in set(v) if v.count(item) > 1]

    def warning(self, txt):
        print(
            "\033[1;35mWARNING: {}".format(txt)
        )
