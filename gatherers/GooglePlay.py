from .Gatherer import Gatherer


class GooglePlay(Gatherer):
    def __init__(self):
        super().__init__()

    # TODO: this either needs to be implemented seriously, or removed altogether
    # I assume this should track Downloads. Can't find any information
    # with regards to this in the Play Store Console!
    def gather(self):
        metrics = dict()

        metrics['ts-android_total'] = 1737
        metrics['uw-android_total'] = 1411
        metrics['tk-android_total'] = 724

        self._send_to_graphite('stats.gauges', 'play', metrics)
