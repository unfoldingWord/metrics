from .Gatherer import Gatherer


class Github(Gatherer):
    def __init__(self):
        super().__init__()

    def gather(self):
        metrics = dict()

        release_api = 'https://api.github.com/repos/unfoldingWord-dev/{0}/releases'
        software = ['translationCore', 'ts-android', 'ts-desktop', 'uw-android']

        for app in software:
            metrics['software_{0}'.format(app)] = 0
            releases = self._get_json_from_url(release_api.format(app))
            for entry in releases:
                if 'assets' in entry:
                    for asset in entry['assets']:
                        metrics['software_{0}'.format(app)] += asset['download_count']

        self._send_to_graphite('stats.gauges', 'github', metrics)

    def log_stats(self):
        github_token = self._get_env('GITHUB_TOKEN')
        self._logger.info(self._get_json_from_url('https://api.github.com/rate_limit', github_token))
