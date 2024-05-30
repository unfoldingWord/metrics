from .Gatherer import Gatherer
from github import Github as Gh
import datetime
from dateutil.relativedelta import *


class Github(Gatherer):
    def __init__(self):
        super().__init__()

        self.github_token = self._get_env('GITHUB_TOKEN')
        self.github_api = Gh(self.github_token)

    def _get_software_release_downloads(self):
        dict_metrics = dict()

        software = ['translationCore', 'ts-android', 'ts-desktop', 'uw-android']

        for app in software:
            dict_metrics['software_{0}'.format(app)] = 0
            obj_releases = self.github_api.get_repo("unfoldingWord-dev/{0}".format(app)).get_releases()

            nr_of_assets = 0
            for release in obj_releases:
                lst_assets = release.get_assets()
                if lst_assets:
                    nr_of_assets += lst_assets.totalCount
                    for asset in lst_assets:
                        dict_metrics['software_{0}'.format(app)] += asset.download_count

        return dict_metrics

    def _get_repository_clones(self):
        lst_orgs = ['unfoldingword']

        today = datetime.datetime.today()
        dt_last_6_months = today + relativedelta(months=-6)

        dict_metrics = dict()

        for org in lst_orgs:
            obj_org = self.github_api.get_organization(org)
            # Get all repo's from orgs
            repos = obj_org.get_repos()

            for repo in repos:

                if (not repo.archived) and repo.size > 0:
                    # For every active (non-archived) and non-empty repo, get activity (commits) from last 6 months
                    total_commits = repo.get_commits(since=dt_last_6_months).totalCount
                    if total_commits > 0:
                        repo_name = repo.name.replace(".", "_")

                        # Get the total amount of commits
                        dict_metrics["repositories.{0}.total_commits".format(repo_name)] = total_commits

                        # Get the amount of clones
                        clones = repo.get_clones_traffic()
                        dict_metrics["repositories.{0}.unique_clones".format(repo_name)] = clones['uniques']
                        dict_metrics["repositories.{0}.total_clones".format(repo_name)] = clones['count']

        return dict_metrics

    def _log_stats(self):
        obj_rate = self.github_api.get_rate_limit()

        dict_metrics = dict()
        for obj in obj_rate.raw_data:
            obj_metrics = {
                "rate_limit.{0}.used".format(obj) : obj_rate.raw_data[obj]["used"],
                "rate_limit.{0}.remaining".format(obj): obj_rate.raw_data[obj]["remaining"]
            }
            dict_metrics.update(obj_metrics)

        return dict_metrics

    def gather(self):

        # We are sending the metrics in batches instead of one big aggregate,
        # to enable Graphite to catch up. Somehow, random metrics appeared to fall through the cracks.
        metrics = self._get_software_release_downloads()
        self._send_to_graphite('stats.gauges', 'github', metrics)

        metrics = self._get_repository_clones()
        self._send_to_graphite('stats.gauges', 'github', metrics)

        metrics = self._log_stats()
        self._send_to_graphite('stats.gauges', 'github', metrics)
