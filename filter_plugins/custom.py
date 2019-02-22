from itertools import groupby
from operator import itemgetter
from cl_vx_config.core import GetConfigVars
import re

getconfigvars = GetConfigVars()


class FilterModule:

    def filters(self):
        return {
            'cluster_to_range': self.cluster_to_range,
            'range_to_cluster': self.range_to_cluster,
            'get_config': self.get_config
            }

    def get_config(self, v):
        method = getattr(getconfigvars, v)

        return method()

    def cluster_to_range(self, v):
        try:
            value = [item.strip() for item in v.split(',')]
        except AttributeError:
            value = [_item for item in v for _item in item.split(',')]

        range_list = []
        for item in value:
            try:
                m = re.match(r'(\w+|\d+)(?<!\d)', item)
                base_name = m.group(0)
            except AttributeError:
                base_name = ''

            range_format = list(
                map(int, item.replace(base_name, '').split('-')))
            if len(range_format) > 1:
                for x in range(range_format[0], range_format[1] + 1):
                    range_list.append(base_name + str(x))
            else:
                range_list.append(base_name + str(range_format[0]))

        return range_list

    def range_to_cluster(self, v):
        if isinstance(v, list):
            value = v
        if isinstance(v, str):
            value = v.replace(' ', '').split(',')

        for item in value:
            try:
                m = re.match(r'(\w+|\d+)(?<!\d)', item)
                base_name = m.group(0)
            except AttributeError:
                base_name = ''

        try:
            range_format = [int(item.replace(base_name, '')) for item in v]
        except ValueError as error:
            return error

        groups = []
        for k, _v in groupby(enumerate(sorted(range_format)),
                             lambda x: x[1]-x[0]):
            groups.append(list(map(itemgetter(1), list(_v))))

        clustered = []
        for k in groups:
            if len(k) > 1:
                format = "{}{}-{}".format(base_name, k[0], k[-1])
            else:
                format = "{}{}".format(base_name, k[0])
            clustered.append(format)

        return ",".join(clustered)
