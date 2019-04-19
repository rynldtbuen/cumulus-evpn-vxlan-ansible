import itertools as iter
import operator as oper

from cl_vx_config.utils import Interface


class Filters:
    ''' Help transfrom data into a correct output,
        use in generating variables '''

    def cluster(self, items, _list=False, join=False):
        '''
        Take a list of elemenets or a string with elemenets.

        Example:
        items=['swp1', 'swp2', 'swp4', 'swp5', 'swp10-11']
        items='swp1, swp2, swp4, swp5, swp10-11'

        If clustred: return values: ['swp1-2', 'swp4-5', 'swp10-11']
        Else: return values: ['swp1', 'swp2', 'swp4', 'swp5', 'swp10-11']
        '''

        def _cluster(items):
            _not_clustered = []
            for item in items:
                iface = Interface(item)
                if isinstance(iface.id, str):
                    start, end = [int(i.strip()) for i in iface.id.split('-')]
                    _items = [iface.base_name + str(r)
                              for r in range(start, end + 1)]
                    for _item in _items:
                        _iface = Interface(_item)
                        _not_clustered.append((_iface.id, _iface.base_name))
                if isinstance(iface.id, int):
                    _not_clustered.append((iface.id, iface.base_name))

            _clustered = []
            for k, v in iter.groupby(_not_clustered, key=lambda x: x[1]):
                _ids = list(map(oper.itemgetter(0), v))
                for _k, _v in iter.groupby(
                        enumerate(sorted(_ids)), lambda x: x[1]-x[0]
                ):
                    group = list(map(oper.itemgetter(1), list(_v)))

                    if len(group) > 1:
                        _clustered.append(
                            "{}{}-{}".format(k, group[0], group[-1])
                        )
                    else:
                        _clustered.append(
                            "{}{}".format(k, group[0])
                        )

            results = []
            if _list:
                for item in sorted(_not_clustered):
                    x = item[1] + str(item[0])
                    results.append(x)
            else:
                for item in sorted(_clustered):
                    results.append(item)

            return results

        if isinstance(items, list):
            return _cluster(items)
        if isinstance(items, str):
            _items = [item.strip() for item in items.split(',')]
            return _cluster(_items)
