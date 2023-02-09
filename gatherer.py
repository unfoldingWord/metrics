import os
import sys
import logging
from dotenv import load_dotenv
# Here are all our gatherer components
from gatherers import *

# in develop only?
load_dotenv()


class UfwMetrics:

    def __init__(self):
        pass
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

    def gather(self):

        if self.get_env_var('SEND_METRICS') == 'false':
            self.logger.warning('Metrics will not be sent to graphite. Environment variable SEND_METRICS set to \'false\'')

        lst_metrics_to_fetch = self.get_env_var('FETCH_METRICS').split(",")

        # Door43 (Lambda status)
        if "door43" in lst_metrics_to_fetch:
            obj_gatherer_d43 = Door43()
            obj_gatherer_d43.gather()

        # Td metrics
        if "td" in lst_metrics_to_fetch:
            obj_gatherer_td = TD()
            obj_gatherer_td.gather()

        # Catalog
        if "catalog" in lst_metrics_to_fetch:
            obj_gatherer_catalog_next = CatalogNext()
            obj_gatherer_catalog_next.gather()

        # Git metrics
        if "github" in lst_metrics_to_fetch:
            obj_gatherer_github = Github()
            obj_gatherer_github.gather()

        # Google play metrics
        if "google_play" in lst_metrics_to_fetch:
            obj_gatherer_gplay = GooglePlay()
            obj_gatherer_gplay.gather()

        # SendGrid stats
        if "sendgrid" in lst_metrics_to_fetch:
            obj_gatherer_sendgrid = Sendgrid()
            obj_gatherer_sendgrid.gather()

        # tX stats
        if "tx" in lst_metrics_to_fetch:
            obj_tx = TX()
            obj_tx.gather()


if __name__ == "__main__":
    obj_metrics = UfwMetrics()
    obj_metrics.gather()
