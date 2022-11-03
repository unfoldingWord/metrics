from .Gatherer import Gatherer
import re
import datetime

# Right now, this module is non-functional.
# TODO: this module needs to be redone, as the API appears to have been overhauled


class Zenhub(Gatherer):
    def __init__(self):
        super().__init__()

    def __get_lanes_metrics(self, lanes, metrics=None):
        if not metrics:
            metrics = dict()

        for lane in lanes['pipelines']:
            sanitized_name = re.sub(r'\W+', '-', lane['name'])
            lane_issues_key = 'lane_issues_{0}'.format(sanitized_name)
            metrics[lane_issues_key] = len(lane['issues'])
            lane_points_key = 'lane_points_{0}'.format(sanitized_name)
            metrics[lane_points_key] = 0
            for issue in lane['issues']:
                if 'estimate' in issue:
                    metrics[lane_points_key] += issue['estimate']['value']
        return metrics

    def __get_graphite_messages(self, metrics, ns):
        messages = list()
        now = datetime.datetime.now().strftime('%s')

        for k, v in metrics.items():
            messages.append('stats.gauges.{0}.{1} {2} {3}\n'.format(ns, k, v, now))

        return messages

    def gather(self):
        # This code is non-functional, will NEVER work this way.
        # Look in dash on stats.gauges.tc_dev.* for how the metrics should look like
        # Metrics borked around 2022-10-26,
        # Error: urllib3.connection:Certificate did not match expected hostname: api.zenhub.io
        zenhub_token = self._get_env('ZENHUB_TOKEN')
        zenhub_api = 'https://api.zenhub.io/p1/repositories/65028237/board?access_token={0}'

        try:
            lanes = self._get_json_from_url(zenhub_api.format(zenhub_token))
            lanes_metrics = self.__get_lanes_metrics(lanes)
            self._logger.info(lanes_metrics)
            lanes_messages = self.__get_graphite_messages(lanes_metrics, 'tc_dev')
            self._send_to_graphite('stats.gauges', 'tc_dev', lanes_messages)
        except:
            self._send_to_graphite('gatherer.errors', 'zenhub', 1)
