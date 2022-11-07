from .Gatherer import Gatherer
import datetime


class Sendgrid(Gatherer):
    def __init__(self):
        super().__init__()

    def gather(self):
        sendgrid_token = self._get_env('SENDGRID_TOKEN')
        sendgrid_api = 'https://api.sendgrid.com/v3/stats?start_date={0}'

        sendgrid_stats = self._get_json_from_url(sendgrid_api.format(
            datetime.datetime.today().strftime('%Y-%m-%d')), auth=sendgrid_token)

        if type(sendgrid_stats) == list:
            sendgrid_metrics = sendgrid_stats[0]['stats'][0]['metrics']

            self._send_to_graphite('stats.gauges', 'sendgrid', sendgrid_metrics)
