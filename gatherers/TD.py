from .Gatherer import Gatherer


class TD(Gatherer):
    # This class is kind of deprecated, as langnames.json is no longer actively updated
    def __init__(self):
        super().__init__()

    def gather(self):
        metrics = dict()

        langnames = self._get_json_from_url('https://td.unfoldingword.org/exports/langnames.json')
        gl_codes = [lang['lc'] for lang in langnames if lang['gw']]
        metrics['langs_all'] = len(langnames)
        metrics['langs_gls'] = len(gl_codes)
        metrics['langs_private_use'] = len([lang for lang in langnames if '-x-' in lang['lc']])

        self._send_to_graphite('stats.gauges', 'td', metrics)
