import os
import sys
import logging
import datetime
from dotenv import load_dotenv
# Here are all our gatherer components
from gatherers import *

# in develop only?
load_dotenv()


class UfwMetrics:

    def __init__(self):
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
        logging.basicConfig()

        this_logger = logging.getLogger()
        this_logger.setLevel(logging.INFO)

        return this_logger

    def get_env_var(self, env_name):
        return os.getenv(env_name, False)

    def gather(self):

        # Door43 (Lambda status)
        obj_gatherer_d43 = Door43()
        obj_gatherer_d43.gather()

        # Td metrics
        obj_gatherer_td = TD()
        obj_gatherer_td.gather()

        # Catalog
        obj_gatherer_catalog_next = CatalogNext()
        obj_gatherer_catalog_next.gather()

        # Git metrics
        obj_gatherer_github = Github()
        # Only get these periodically, to stay under our rate limit
        if datetime.datetime.now().minute == 0 and datetime.datetime.now().hour in [8, 12, 16, 20]:
            obj_gatherer_github.gather()

        # Load Github var and log our rate_limit details
        obj_gatherer_github.log_stats()

        # Google play metrics
        obj_gatherer_gplay = GooglePlay()
        obj_gatherer_gplay.gather()

        # SendGrid stats
        obj_gatherer_sendgrid = Sendgrid()
        obj_gatherer_sendgrid.gather()


if __name__ == "__main__":
    obj_metrics = UfwMetrics()
    obj_metrics.gather()
