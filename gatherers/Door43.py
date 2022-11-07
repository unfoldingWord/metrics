from .Gatherer import Gatherer


class Door43(Gatherer):
    def __init__(self):
        super().__init__()

    def gather(self):
        d43api_api = 'https://api.door43.org/v3/lambda/status'
        status = self._get_json_from_url(d43api_api)

        metrics = dict()

        api_status = {'complete': 0,
                      'in-progress': 1,
                      'incomplete': 1,
                      'error': 2,
                      }

        for endpoint in status['functions']:
            name = endpoint['name'].replace('.', '_')
            try:
                metrics[name] = api_status[endpoint['status']]
            except KeyError:
                metrics[name] = 3

        self._send_to_graphite('stats.gauges', 'door43_api', metrics)
