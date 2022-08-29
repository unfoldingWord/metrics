import os
import re
import sys
import socket
import statsd
import logging
import datetime
import requests
from dotenv import load_dotenv
import json

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
        # TODO: Is this list complete? Probably this is not even relevant anymore.

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
            "tasks_api": "https://api.github.com/repos/unfoldingWord-dev/translationCore/issues?labels=Task&page={0}",
            "zenhub_api": "https://api.zenhub.io/p1/repositories/65028237/board?access_token={0}",
            "sendgrid_api": "https://api.sendgrid.com/v3/stats?start_date={0}",
            "d43api_api": "https://api.door43.org/v3/lambda/status",
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

    def catalog_next(self):
        url = 'https://git.door43.org/api/catalog/v5/search'
        catalog_data = json.loads(requests.get(url).text)

        lst_gls = list()
        dict_identifiers = dict()
        dict_subjects = dict()
        dict_bp_collector = dict()

        lst_owner_ignore = ["test_org", "test_org2", "test_org3"]

        all_resources = 0
        for item in catalog_data["data"]:

            if item["owner"] in lst_owner_ignore:
                # Skip items from 'junk' owners ('test' or otherwise)
                continue

            all_resources += 1

            language = item["language"]

            if language not in lst_gls and item["language_is_gl"] is True:
                lst_gls.append(language)

            # 1) Resources by identifier
            lst_identifier = item["name"].lower().split("_")
            if len(lst_identifier) == 2:
                identifier = lst_identifier[1]
            else:
                identifier = lst_identifier[0]

            if identifier not in dict_identifiers:
                dict_identifiers[identifier] = 1
            else:
                dict_identifiers[identifier] += 1

            # 2) Resources by subject
            subject = item["subject"]
            if subject not in dict_subjects:
                dict_subjects[subject] = 1
            else:
                dict_subjects[subject] += 1

            # 3) Book package fact collecting
            if language not in dict_bp_collector:
                dict_bp_collector[language] = {"has_ta": False,
                                               "has_tw": False,
                                               "has_tn": False,
                                               "has_tq": False,
                                               "aligned_books": list()
                                               }

            # 3a) GL or not
            dict_bp_collector[language]["is_gl"] = item["language_is_gl"]

            # 3b) Check for Resources
            if identifier == "ta":
                dict_bp_collector[language]["has_ta"] = True
            elif identifier == "tw":
                dict_bp_collector[language]["has_tw"] = True
            elif identifier == "tn":
                dict_bp_collector[language]["has_tn"] = True
            elif identifier == "tq":
                dict_bp_collector[language]["has_tq"] = True

            # 3c) Check for Aligned Bible
            if item["subject"] == "Aligned Bible":

                for book in item["alignment_counts"]:
                    if book not in dict_bp_collector[language]["aligned_books"]:
                        if item["alignment_counts"][book] > 0:
                            dict_bp_collector[language]["aligned_books"].append(book)

        # 4) Building the actual metrics dictionary
        metrics = dict()

        metrics["total_langs"] = len(dict_bp_collector)
        metrics["gls_with_content"] = len(lst_gls)

        # 4a) Resources by identifier
        for identifier in dict_identifiers:
            metrics['resources_{}_langs'.format(identifier)] = dict_identifiers[identifier]

        # 4b) Resources by subject
        for subject in dict_subjects:
            metrics['subject_{}'.format(subject)] = dict_subjects[subject]

        metrics["all_resources"] = len(catalog_data["data"])

        # 4c) Book package counting
        all_bpfs = 0
        for language in dict_bp_collector:
            item = dict_bp_collector[language]
            # If this language has a tA, a tN, a tQ, and a tW resource,
            # then, for every aligned book in the Aligned Bible for this language (contains the '\\zaln-s' tag),
            # we increment the number of completed Book Packages.
            if item["has_ta"] and item["has_tn"] and item["has_tq"] and item["has_tw"]:
                bp_per_language = len(item["aligned_books"])

                if bp_per_language > 0:
                    all_bpfs += bp_per_language

                    if item["is_gl"] is True:
                        metrics['completed_bps_per_language.gl.{}'.format(language)] = bp_per_language
                    else:
                        metrics['completed_bps_per_language.ol.{}'.format(language)] = bp_per_language

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
        return metrics

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

    # TODO: this needs to be implemented in reality.
    # I assume this should track Downloads. Can't find any information
    # with regards to this in the Play Store Console!
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

        # # D43 API metrics
        d43api_api = self.get_api_url("d43api_api")

        status = self.get_json_from_url(d43api_api)
        status_metrics = self.d43api(status)
        self.push_to_statsd(status_metrics, prefix="door43_api")

        # Td metrics
        td_metrics = self.td()
        self.push_to_statsd(td_metrics, prefix="td")

        # Catalog
        catalog_metrics = self.catalog_next()
        self.push_to_statsd(catalog_metrics, prefix="catalog_next")

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
