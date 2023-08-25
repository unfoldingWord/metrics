import os
import sys
import logging
from dotenv import load_dotenv
# Here are all our gatherer components
from gatherers import *
import graphyte

# in develop only?
load_dotenv()


class UfwMetrics:

    def __init__(self):
        # Init graphite
        graphite_host = self.get_env_var('GRAPHITE_HOST')
        graphyte.init(graphite_host)

        self.logger = self.init_logger()

        self.check_environment_variables()

    def check_environment_variables(self):
        lst_env_vars = [
            "GITHUB_TOKEN",
            "SENDGRID_TOKEN",
            "ZENHUB_TOKEN",
            "STATSD_HOST",
            "GRAPHITE_HOST",
        ]

        for env_var in lst_env_vars:
            if not self.get_env_var(env_var):
                self.logger.warning('Environment variable {0} not found.'.format(env_var))
                sys.exit(1)

    def _send_to_graphite(self, prefix, metric, value, timestamp=None):

        ts_log = ' (ts: ' + str(timestamp) + ')' if timestamp else ''

        self.logger.info(prefix + '.' + metric + ': ' + str(value) + ts_log)

        # If we don't want to send the metrics to Graphite, we allow them to be logged, but we don't actually send them
        if self.get_env_var('SEND_METRICS') == 'false':
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

    def init_logger(self):
        this_logger = logging.getLogger()

        if not this_logger.hasHandlers():
            c_handler = logging.StreamHandler()
            if os.getenv('STAGE', False) == 'dev':
                c_handler.setLevel(logging.DEBUG)
                this_logger.setLevel(logging.DEBUG)
            else:
                c_handler.setLevel(logging.INFO)
                this_logger.setLevel(logging.INFO)

            log_format = '%(asctime)s  %(levelname)-8s %(message)s'
            c_format = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
            c_handler.setFormatter(c_format)

            this_logger.addHandler(c_handler)

        return this_logger

    def get_env_var(self, env_name):
        return os.getenv(env_name, False)

    def _gatherer_can_run(self, metric_name):
        if self.get_env_var('FETCH_METRICS'):
            lst_metrics_to_fetch = self.get_env_var('FETCH_METRICS').replace(" ", "").split(",")

            if metric_name not in lst_metrics_to_fetch:
                return False

        # FETCH_METRICS is not defined, or the metric name DOES occur in lst_metrics_to_fetch
        # In either case, we can run!
        return True

    def gather(self):

        if self.get_env_var('SEND_METRICS') == 'false':
            self.logger.warning('Metrics will not be sent to graphite. '
                                'Environment variable SEND_METRICS set to \'false\'')

        metrics_ran = 0

        # Door43 (Lambda status)
        if self._gatherer_can_run("door43"):
            metrics_ran += 1

            obj_gatherer_d43 = Door43()
            obj_gatherer_d43.gather()

        # Td metrics
        if self._gatherer_can_run("td"):
            metrics_ran += 1

            obj_gatherer_td = TD()
            obj_gatherer_td.gather()

        # Catalog
        if self._gatherer_can_run("catalog"):
            metrics_ran += 1

            obj_gatherer_catalog_next = CatalogNext()
            obj_gatherer_catalog_next.gather()

        # GitHub metrics
        if self._gatherer_can_run("github"):
            metrics_ran += 1

            obj_gatherer_github = Github()
            obj_gatherer_github.gather()

        # Google play metrics
        if self._gatherer_can_run("google_play"):
            metrics_ran += 1

            obj_gatherer_gplay = GooglePlay()
            obj_gatherer_gplay.gather()

        # SendGrid stats
        if self._gatherer_can_run("sendgrid"):
            metrics_ran += 1

            obj_gatherer_sendgrid = Sendgrid()
            obj_gatherer_sendgrid.gather()

        # tX stats
        if self._gatherer_can_run("tx"):
            metrics_ran += 1

            obj_tx = TX()
            obj_tx.gather()

        self.logger.info('Ran {0} metric gatherer(s)'.format(metrics_ran))
        self._send_to_graphite('stats.gauges', 'metrics.gathered', int(metrics_ran))


if __name__ == "__main__":
    obj_metrics = UfwMetrics()
    obj_metrics.gather()
