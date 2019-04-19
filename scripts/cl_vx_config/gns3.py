import requests
import json


base_url = "http://10.0.0.254:3080/v2"


class GNS3Project:

    def __init__(self, base_url, project_name):
        self.base_url = base_url
        # self.url = '{}/{}'.format(base_url, 'projects')
        self.project_name = project_name
        self.project_url = (
            '{}/{}'.format(self.base_url + '/projects', self._get_project_id)
        )

    def __iter__(self):
        return iter(requests.get(self.base_url + '/projects').json())

    @property
    def _get_project_id(self):
        for item in self.__iter__():
            if item['name'] == self.project_name:
                return item['project_id']

    def create(self):
        r = requests.post(self.url, params={'name': self.project_name})
        try:
            return r.json()['message']
        except KeyError:
            return r.json()

    def delete(self):
        r = requests.delete(self.project_url)
        try:
            return (r.json()['message']).replace(
                'ID None', '"{}"'.format(self.project_name))
        except json.decoder.JSONDecodeError:
            return (
                'Project "{}" has been delated'.format(self.project_name)
            )

    def open(self):
        r = requests.post(self.project_url + '/open', '{}')
        return r.json()

    def close(self):
        r = requests.post(self.project_url + '/close', '{}')
        return r.json()


class GNS3Node(GNS3Project):

    def __init__(
        self, base_url, project_name, name, type
    ):
        super().__init__(base_url, project_name)
        self.name = name
        self.type = type
        self.compute_id = 'local'
        self.nodes_url = self.project_url + '/nodes'
        self.node_id_url = (
            '{}/{}'.format(self.project_url + '/nodes', self._get_node_id)
        )

    @property
    def _get_computes(self):
        r = requests.get(self.base_url + '/computes')
        return r.json()

    def __list__(self):
        return iter(requests.get(self.nodes_url).json())

    @property
    def _get_node_id(self):
        for item in self.__list__():
            if item['node_name'] == self.node_name:
                return item['node_id']

    @property
    def _get_appliances(self):
        return iter(requests.get(self.base_url + '/appliances').json())

    def create(self):
        data = {
            'compute_id': self.compute_id,
            'name': self.name,
            'node_type': self.type
        }
        r = requests.post(self.nodes_url, params=data)
        return r.json()
