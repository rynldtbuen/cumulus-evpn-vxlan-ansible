from cumulus_vxconfig.configvars import ConfigVars


class FilterModule:

    def filters(self):
        return {
            'get_config': self.get_config,
            'duplicate_items': self.duplicate_items
        }

    def get_config(self, v):
        method = getattr(ConfigVars(), v)
        return method()

    def duplicate_items(self, v):
        return [item for item in set(v) if v.count(item) > 1]
