# import re
# from cumulus_custom_plugins.helpers import glob_to_uncluster


class FilterModule:

    def filters(self):
        return {
            'duplicate_items': self.duplicate_items,
        }

    def duplicate_items(self, items):
        uniq_items = set(items)
        return [i for i in uniq_items if items.count(i) > 1]
