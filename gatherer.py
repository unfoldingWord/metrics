import os
import re
import sys
import socket
import statsd
import logging
import datetime
import io
import requests
import zipfile
from dotenv import load_dotenv

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

    def get_devs(self):
        # TODO: Is this list complete?

        devs = [('bspidel', 3),
                ('klappy', 0),
                ('RoyalSix', 6),
                ('mannycolon', 6),
                ('richmahn', 5),
                ('PhotoNomad0', 5)
                ]

        return devs

    def get_api_url(self, api_id):
        dict_apis = {
            "milestones_api": "https://api.github.com/repos/unfoldingWord-dev/translationCore/milestones",
            # "issues_api": "https://api.github.com/repos/unfoldingWord-dev/translationCore/issues?milestone={0}",
            "tasks_api": "https://api.github.com/repos/unfoldingWord-dev/translationCore/issues?labels=Task&page={0}",
            "zenhub_api": "https://api.zenhub.io/p1/repositories/65028237/board?access_token={0}",
            "sendgrid_api": "https://api.sendgrid.com/v3/stats?start_date={0}",
            "d43api_api": "https://api.door43.org/v3/lambda/status",
            "catalog_api": "https://api.door43.org/v3/catalog.json",
            "release_api": 'https://api.github.com/repos/unfoldingWord-dev/{0}/releases'
        }

        if not api_id or api_id not in dict_apis.keys():
            return None

        return dict_apis[api_id]

    def init_logger(self):
        logging.basicConfig()

        this_logger = logging.getLogger()
        this_logger.setLevel(logging.INFO)

        return this_logger

    def get_env_var(self, env_name):
        return os.getenv(env_name, False)

    def get_graphite_messages(self, metrics, ns):
        messages = list()
        now = datetime.datetime.now().strftime('%s')

        for k, v in metrics.items():
            messages.append('stats.gauges.{0}.{1} {2} {3}\n'.format(ns, k, v, now))

        return messages

    def get_json_from_url(self, url, token="", auth="", params=""):
        if token:
            raw = requests.get(url, auth=('token', token))
        elif auth:
            raw = requests.get(url, headers={'Authorization': auth})
        elif params:
            raw = requests.get(url, params=params)
        else:
            raw = requests.get(url)

        return raw.json()

    def push_to_statsd(self, metrics, port=8125, prefix=''):
        host = self.get_env_var("STATSD_HOST")

        stats = statsd.StatsClient(host, port, prefix=prefix)
        for k, v in metrics.items():
            stats.gauge(k, v)

    def push_to_graphite(self, messages, port=2003):
        host = self.get_env_var("GRAPHITE_HOST")

        for m in messages:
            sock = socket.socket()
            sock.connect((host, port))
            sock.sendall(m.encode('utf-8'))
            sock.close()

    def get_alignment_counts(self, lc, cdn_path):
        # Receive language name and cdn path to zip file for language
        # Return list of projects with numbers of alignments
        counts = {}
        if cdn_path.count('.zip') > 0:
            response = requests.get(cdn_path)
            with zipfile.ZipFile(io.BytesIO(response.content)) as the_zip:
                for zip_info in the_zip.infolist():
                    filename = zip_info.filename
                    if filename.count('.usfm') > 0:
                        with the_zip.open(zip_info) as the_file:
                            book = str(filename)[-8: -5].lower()
                            slug = lc + '_' + book
                            the_text = str(the_file.read())
                            count = the_text.count('\\zaln-s')
                            if count > 0:
                                counts[slug] = count
        return counts

    def catalog(self, gl_codes, metrics=None):
        if not metrics:
            metrics = dict()

        catalog_api = self.get_api_url("catalog_api")

        catalog = self.get_json_from_url(catalog_api)
        metrics['total_langs'] = len(catalog['languages'])
        metrics['gls_with_content'] = len([x for x in catalog['languages'] if x['identifier'] in gl_codes])
        all_resources = 0
        all_bpfs = 0
        for x in catalog['languages']:
            for y in x['resources']:
                all_resources += 1
                # Resources by identifier
                if not 'resources_{}_langs'.format(y['identifier']) in metrics:
                    metrics['resources_{}_langs'.format(y['identifier'])] = 0
                metrics['resources_{}_langs'.format(y['identifier'])] += 1
                # Resources by subject
                if not 'subject_{}'.format(y['subject']) in metrics:
                    metrics['subject_{}'.format(y['subject'])] = 0
                metrics['subject_{}'.format(y['subject'])] += 1
        metrics['all_resources'] = all_resources
        counts = {}
        for lang in catalog['languages']:  # look at all the languages
            is_ta = False
            is_tn = False
            is_tq = False
            is_tw = False
            lc = lang['identifier']
            for res in lang['resources']:
                resource = res['identifier']
                subject = res['subject']
                if subject == 'Aligned Bible':
                    for fmt in res['formats']:
                        cdn_path = fmt['url']
                        update_counts = self.get_alignment_counts(lc, cdn_path)
                        if len(update_counts) > 0:
                            counts.update(update_counts)
                elif resource == 'ta':
                    is_ta = True
                elif resource == 'tn':
                    is_tn = True
                elif resource == 'tq':
                    is_tq = True
                elif resource == 'tw':
                    is_tw = True
            # end of language
            if is_ta and is_tn and is_tq and is_tw:
                for key in counts:
                    if key.find(lc) == 0:
                        if counts[key] > 0:
                            all_bpfs += 1
        metrics['completed_bps'] = all_bpfs

        self.logger.info(metrics)
        return metrics

    def td(self, metrics=None):
        if not metrics:
            metrics = dict()

        langnames = self.get_json_from_url('https://td.unfoldingword.org/exports/langnames.json')
        gl_codes = [x['lc'] for x in langnames if x['gw']]
        metrics['langs_all'] = len(langnames)
        metrics['langs_gls'] = len(gl_codes)
        metrics['langs_private_use'] = len([x for x in langnames if '-x-' in x['lc']])

        self.logger.info(metrics)
        return metrics, gl_codes

    def github(self, metrics=None):
        if not metrics:
            metrics = dict()

        release_api = self.get_api_url("release_api")
        software = ['translationCore', 'ts-android', 'ts-desktop', 'uw-android']
        for x in software:
            metrics['software_{0}'.format(x)] = 0
            releases = self.get_json_from_url(release_api.format(x))
            for entry in releases:
                if 'assets' in entry:
                    for asset in entry['assets']:
                        metrics['software_{0}'.format(x)] += asset['download_count']
        self.logger.info(metrics)
        return metrics

    def play(self, metrics=None):
        if not metrics:
            metrics = dict()

        metrics['ts-android_total'] = 1737
        metrics['uw-android_total'] = 1411
        metrics['tk-android_total'] = 724
        self.logger.info(metrics)
        return metrics

    def get_hours_remaining(self, title):
        number = title.split()[0].strip('[]')
        try:
            hours = int(number)
        except ValueError:
            hours = 0

        return hours

    def get_days_remaining(self, total_time_left):
        # Subtract 2 days because of how the milestone records the due date
        days_left = total_time_left.days
        if days_left < 3:
            return 0
        if days_left <= 8:
            return days_left - 2
        if days_left > 8:
            return days_left - 4

    # @TODO: this whole check possibly can be removed. All information always returns 0.
    def get_available_hours(self, multiplier, metrics=None):
        if not metrics:
            metrics = dict()

        devs = self.get_devs()

        for dev in devs:
            metrics['hours_avail_{0}'.format(dev[0])] = (dev[1] * multiplier)

        return metrics

    def get_milestone_time_left(self, github_token):
        milestones_api = self.get_api_url("milestones_api")

        milestone_json = self.get_json_from_url(milestones_api, github_token)
        end_date = milestone_json[0]['due_on']
        y, m, d = [int(x) for x in end_date.split('T')[0].split('-')]
        return datetime.datetime(y, m, d) - datetime.datetime.today()

    def get_task_metrics(self, tasks, metrics=None):
        # Initialize to zero so that graphite gets a zero even if a dev has no tasks
        if not metrics:
            metrics = dict()

            devs = self.get_devs()

            for dev in devs:
                metrics['hours_{0}'.format(dev[0])] = 0

        for item in tasks:
            if 'assignees' not in item:
                continue

            for user in item['assignees']:
                hours_key = 'hours_{0}'.format(user['login'])
                if hours_key not in metrics:
                    continue

                metrics[hours_key] += self.get_hours_remaining(item['title'].strip())
        return metrics

    def get_lanes_metrics(self, lanes, metrics=None):
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

    def d43api(self, status, metrics=None):
        if not metrics:
            metrics = dict()

        api_status = {'complete': 0,
                      'in-progress': 1,
                      'incomplete': 1,
                      'error': 2,
                      }

        for endpoint in status['functions']:
            name = endpoint['name'].replace('.', '_')
            try:
                metrics[name] = api_status[endpoint['status']]
            except KeyError:
                metrics[name] = 3

        self.logger.info(metrics)
        return metrics

    def gather(self):

        # D43 API metrics
        d43api_api = self.get_api_url("d43api_api")

        status = self.get_json_from_url(d43api_api)
        status_metrics = self.d43api(status)
        self.push_to_statsd(status_metrics, prefix="door43_api")

        # Td metrics
        td_metrics, gl_codes = self.td()
        self.push_to_statsd(td_metrics, prefix="td")
        catalog_metrics = self.catalog(gl_codes)
        self.push_to_statsd(catalog_metrics, prefix="door43_catalog")

        # Git metrics
        # Only get these periodically, to stay under our rate limit
        if datetime.datetime.now().minute == 0 and datetime.datetime.now().hour in [8, 12, 16, 20]:
            github_metrics = self.github()
            self.push_to_statsd(github_metrics, prefix="github")

        # Google play metrics
        play_metrics = self.play()
        self.push_to_statsd(play_metrics, prefix="play")

        # Load Github var and log our rate_limit details
        github_token = self.get_env_var('GITHUB_TOKEN')
        self.logger.info(self.get_json_from_url('https://api.github.com/rate_limit', github_token))

        # tC Dev Hour Metrics
        hour_metrics = dict()
        for x in [1, 2, 3]:
            tasks_api = self.get_api_url("tasks_api")

            tasks = self.get_json_from_url(tasks_api.format(x), github_token)
            hour_metrics = self.get_task_metrics(tasks, hour_metrics)

        time_left = self.get_milestone_time_left(github_token)
        days_left = self.get_days_remaining(time_left)
        hour_metrics = self.get_available_hours(days_left, hour_metrics)
        self.logger.info(hour_metrics)
        hour_messages = self.get_graphite_messages(hour_metrics, 'tc_dev')
        self.push_to_graphite(hour_messages)

        # tC Dev Lane Metrics
        zenhub_token = self.get_env_var('ZENHUB_TOKEN')
        zenhub_api = self.get_api_url("zenhub_api")

        lanes = self.get_json_from_url(zenhub_api.format(zenhub_token))
        lanes_metrics = self.get_lanes_metrics(lanes)
        self.logger.info(lanes_metrics)
        lanes_messages = self.get_graphite_messages(lanes_metrics, 'tc_dev')
        self.push_to_graphite(lanes_messages)

        # SendGrid stats
        sendgrid_token = self.get_env_var('SENDGRID_TOKEN')
        sendgrid_api = self.get_api_url("sendgrid_api")

        sendgrid_stats = self.get_json_from_url(sendgrid_api.format(
            datetime.datetime.today().strftime('%Y-%m-%d')), auth=sendgrid_token)
        if type(sendgrid_stats) == list:
            sendgrid_metrics = sendgrid_stats[0]['stats'][0]['metrics']
            self.logger.info(sendgrid_metrics)

            self.push_to_statsd(sendgrid_metrics, prefix="sendgrid")


if __name__ == "__main__":
    obj_metrics = UfwMetrics()
    obj_metrics.gather()
