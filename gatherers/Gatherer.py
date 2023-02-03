import graphyte
import os
import logging
import requests


class Gatherer:
    def __init__(self):
        graphite_host = self._get_env('GRAPHITE_HOST')

        # Init graphite
        graphyte.init(graphite_host)

        # Init logging
        self._logger = logging.getLogger()

    def _send_to_graphite(self, prefix, metric, value, timestamp=None):

        ts_log = ' (ts: ' + str(timestamp) + ')' if timestamp else ''

        self._logger.info(prefix + '.' + metric + ': ' + str(value) + ts_log)

        # If we don't want to send the metrics to Graphite, we allow them to be logged, but we don't actually send them
        if self._get_env('SEND_METRICS') == 'false':
            return

        # TODO: needs better exception handling
        if type(value) is dict:
            for key in value:
                full_metric = prefix + '.' + metric + '.' + key
                the_val = value[key]
                try:
                    graphyte.send(full_metric, the_val)
                except:
                    print(full_metric + ': ' + str(the_val))

        elif type(value) is int:
            full_metric = prefix + '.' + metric
            graphyte.send(full_metric, value, timestamp=timestamp)

    def _get_env(self, env):
        env_var = os.getenv(env, False)
        if not env_var:
            raise RuntimeError('Missing environment variable {}'.format(env))

        return env_var

    def _get_json_from_url(self, url, token="", auth=""):
        # Basic headers
        req_headers = {
            'User-Agent': 'MetricsGatherer/1.0; https://github.com/unfoldingWord/metrics'
        }

        if token:
            raw = requests.get(url, auth=('token', token), headers=req_headers)
        elif auth:
            req_headers['Authorization'] = auth
            raw = requests.get(url, headers=req_headers)
        else:
            raw = requests.get(url, headers=req_headers)

        return raw.json()
