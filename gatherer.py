import os
import re
import sys
import json
import socket
import statsd
import logging
import requests
import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

devs = [ ('bspidel', 2),
         ('klappy', 5),
         ('RoyalSix', 6),
         ('mannycolon', 6),
         ('richmahn', 6),
         ('PhotoNomad0', 6)
       ]
api_status = { 'complete': 0,
               'in-progress': 1,
               'incomplete': 1,
               'error': 2,
             }
milestones_api = "https://api.github.com/repos/unfoldingWord-dev/translationCore/milestones"
issues_api = "https://api.github.com/repos/unfoldingWord-dev/translationCore/issues?milestone={0}"
tasks_api = "https://api.github.com/repos/unfoldingWord-dev/translationCore/issues?labels=Task&page={0}"
zenhub_api = "https://api.zenhub.io/p1/repositories/65028237/board?access_token={0}"
sendgrid_api = "https://api.sendgrid.com/v3/stats?start_date={0}"
d43api_api = "https://api.door43.org/v3/lambda/status"

def get_env_var(env_name):
    env_variable = os.getenv(env_name, False)
    if not env_variable:
        logger.warn('Environment variable {0} not found.'.format(env_name))
        sys.exit(1)
    return env_variable

def getGraphiteMessages(metrics, ns):
    messages = []
    now = datetime.datetime.now().strftime('%s')
    for k,v in metrics.items():
        messages.append('stats.gauges.{0}.{1} {2} {3}\n'.format(ns, k, v, now))
    return messages

def getJSONfromURL(url, token="", auth=""):
    if token:
        raw = requests.get(url, auth=('token', token))
    if auth:
        raw = requests.get(url, headers={'Authorization': auth})
    else:
        raw = requests.get(url)
    return raw.json()

def push(metrics, host='localhost', port=8125, prefix=''):
    stats = statsd.StatsClient(host, port, prefix=prefix)
    for k,v in metrics.items():
        stats.gauge(k, v)

def pushGraphite(messages, host='127.0.0.1', port=2003):
    for m in messages:
        sock = socket.socket()
        sock.connect((host, port))
        sock.sendall(m.encode('utf-8'))
        sock.close()

def catalog(gl_codes, metrics={}):
    catalog = getJSONfromURL('https://api.door43.org/v3/catalog.json')
    metrics['total_langs'] = len(catalog['languages'])
    metrics['gls_with_content'] = len([x for x in catalog['languages'] if x['identifier'] in gl_codes])
    all_resources = 0
    for x in catalog['languages']:
        for y in x['resources']:
            all_resources += 1
            if not 'resources_{}_langs'.format(y['identifier']) in metrics:
                metrics['resources_{}_langs'.format(y['identifier'])] =0
            metrics['resources_{}_langs'.format(y['identifier'])] +=1
    metrics['all_resources'] = all_resources
    logger.info(metrics)
    return metrics

def tD(metrics={}):
    langnames = getJSONfromURL('https://td.unfoldingword.org/exports/langnames.json')
    gl_codes = [x['lc'] for x in langnames if x['gw']]
    metrics['langs_all'] = len(langnames)
    metrics['langs_gls'] = len(gl_codes)
    metrics['langs_private_use'] = len([x for x in langnames if '-x-' in x['lc']])
    logger.info(metrics)
    return (metrics, gl_codes)

def github(metrics={}):
    release_api = 'https://api.github.com/repos/unfoldingWord-dev/{0}/releases'
    software = ['translationCore', 'ts-android', 'ts-desktop', 'uw-android']
    for x in software:
        metrics['software_{0}'.format(x)] = 0
        releases = getJSONfromURL(release_api.format(x))
        for entry in releases:
            if 'assets' in entry:
                for asset in entry['assets']:
                    metrics['software_{0}'.format(x)] += asset['download_count']
    logger.info(metrics)
    return metrics

def play(metrics={}):
    metrics['ts-android_total'] = 1737
    metrics['uw-android_total'] = 1411
    metrics['tk-android_total'] = 724
    logger.info(metrics)
    return metrics

def getHoursRemaining(title):
    if title.startswith('['):
        number = title.split()[0].strip('[]')
        try:
            hours = int(number)
        except ValueError:
            hours = 0
    return hours

def getDaysRemaining(timeLeft):
    # Subtract 2 days because of how the milestone records the due date
    daysLeft = timeLeft.days
    if daysLeft < 3:
        return 0
    if daysLeft <= 8:
        return daysLeft - 2
    if daysLeft > 8:
        return daysLeft - 4

def getAvailableHours(multiplier, metrics={}):
    for dev in devs:
        metrics['hours_avail_{0}'.format(dev[0])] = (dev[1] * multiplier)
    return metrics

def getMilestoneTimeLeft():
    milestone_json = getJSONfromURL(milestones_api, github_token)
    endDate = milestone_json[0]['due_on']
    y, m, d = [int(x) for x in endDate.split('T')[0].split('-')]
    return datetime.datetime(y, m, d) - datetime.datetime.today()

def getTaskMetrics(tasks, metrics={}):
    # Initialize to zero so that graphite gets a zero even if a dev has no tasks
    if not metrics:
        for dev in devs:
            metrics['hours_{0}'.format(dev[0])] = 0
    for item in tasks:
        if not 'assignees' in item: continue
        for user in item['assignees']:
            hours_key = 'hours_{0}'.format(user['login'])
            if hours_key not in metrics: continue
            metrics[hours_key] += getHoursRemaining(item['title'].strip())
    return metrics

def getLanesMetrics(lanes, metrics={}):
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

def d43api(status, metrics={}):
    for endpoint in status['functions']:
        name = endpoint['name'].replace('.', '_')
        try:
            metrics[name] = api_status[endpoint['status']]
        except KeyError:
            metrics[name] = 3
    logger.info(metrics)
    return metrics


if __name__ == "__main__":
    logging.basicConfig()
    status = getJSONfromURL(d43api_api)
    status_metrics = d43api(status)
    push(status_metrics, prefix="door43_api")
    td_metrics, gl_codes = tD()
    push(td_metrics, prefix="td")
    catalog_metrics = catalog(gl_codes)
    push(catalog_metrics, prefix="door43_catalog")
    github_metrics = github()
    push(github_metrics, prefix="github")
    play_metrics = play()
    push(play_metrics, prefix="play")

    # Load Github var and log our rate_limit details
    github_token = get_env_var('GITHUB_TOKEN')
    logger.info(getJSONfromURL('https://api.github.com/rate_limit'))

    # tC Dev Hour Metrics
    hour_metrics = {}
    for x in [1, 2, 3]:
       tasks = getJSONfromURL(tasks_api.format(x), github_token)
       hour_metrics = getTaskMetrics(tasks, hour_metrics)
    timeLeft = getMilestoneTimeLeft()
    daysLeft = getDaysRemaining(timeLeft)
    hour_metrics = getAvailableHours(daysLeft, hour_metrics)
    logger.info(hour_metrics)
    hour_messages = getGraphiteMessages(hour_metrics, 'tc_dev')
    pushGraphite(hour_messages)

    # tC Dev Lane Metrics
    zenhub_token = get_env_var('ZENHUB_TOKEN')
    lanes = getJSONfromURL(zenhub_api.format(zenhub_token))
    lanes_metrics = getLanesMetrics(lanes)
    logger.info(lanes_metrics)
    lanes_messages = getGraphiteMessages(lanes_metrics, 'tc_dev')
    pushGraphite(lanes_messages)

    # SendGrid stats
    sendgrid_token = get_env_var('SENDGRID_TOKEN')
    sendgrid_stats = getJSONfromURL(sendgrid_api.format(
                       datetime.datetime.today().strftime('%Y-%m-%d')), auth=sendgrid_token)
    if sendgrid_stats:
        sendgrid_metrics = sendgrid_stats[0]['stats'][0]['metrics']
        logger.info(sendgrid_metrics)
        push(sendgrid_metrics, prefix="sendgrid")
