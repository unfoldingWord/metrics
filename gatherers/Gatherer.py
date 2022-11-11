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

    def _send_to_graphite(self, prefix, metric, value):

        self._logger.info(prefix + '.' + metric + ': ' + str(value))

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
            graphyte.send(full_metric, value)

    def _get_env(self, env):
        env_var = os.getenv(env, False)
        if not env_var:
            raise RuntimeError('Missing environment variable {}'.format(env))

        return env_var

    # I don't like this function
    def _get_json_from_url(self, url, token="", auth=""):
        if token:
            raw = requests.get(url, auth=('token', token))
        elif auth:
            raw = requests.get(url, headers={'Authorization': auth})
        else:
            raw = requests.get(url)

        return raw.json()
