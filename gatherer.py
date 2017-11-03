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

devs = ['bspidel', 'klappy', 'RoyalSix', 'mannycolon', 'richmahn', 'PhotoNomad0']
milestones_api = "https://api.github.com/repos/unfoldingWord-dev/translationCore/milestones"
issues_api = "https://api.github.com/repos/unfoldingWord-dev/translationCore/issues?milestone={0}"
tasks_api = "https://api.github.com/repos/unfoldingWord-dev/translationCore/issues?labels=Task"
zenhub_api = "https://api.zenhub.io/p1/repositories/65028237/board?access_token={0}"
sendgrid_api = "https://api.sendgrid.com/v3/stats?start_date={0}"

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
            for asset in entry['assets']:
                metrics['software_{0}'.format(x)] += asset['download_count']
    logger.info(metrics)
    return metrics

def play(metrics={}):
    metrics['ts-android_total'] = 1698
    metrics['uw-android_total'] = 1393
    metrics['tk-android_total'] = 713
    logger.info(metrics)
    return metrics

def getHoursRemaining(title):
    hours = 0
    if title.startswith('['):
        hours = int(title.split()[0].strip('[]'))
    return hours

def getMilestoneMetrics(issues, metrics={}):
    for item in issues:
        hours_key = 'hours_{0}'.format(item['assignee']['login'])
        issues_key = 'issues_{0}'.format(item['assignee']['login'])
        # Initialize variables
        if hours_key not in metrics:
            metrics[hours_key] = 0
        if issues_key not in metrics:
            metrics[issues_key] = 0
        # Increment
        metrics[hours_key] += getHoursRemaining(item['title'].strip())
        metrics[issues_key] += 1
    return metrics

def getMilestones():
    milestone_json = getJSONfromURL(milestones_api, github_token)
    return [x['number'] for x in milestone_json]

def getTaskMetrics(tasks, metrics={}):
    # Initialize to zero so that graphite gets a zero even if a dev has no tasks
    for dev in devs:
       metrics['hours_{0}'.format(dev)] = 0
    for item in tasks:
        hours_key = 'hours_{0}'.format(item['assignee']['login'])
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


if __name__ == "__main__":
    logging.basicConfig()
    td_metrics, gl_codes = tD()
    push(td_metrics, prefix="td")
    catalog_metrics = catalog(gl_codes)
    push(catalog_metrics, prefix="door43_catalog")
    github_metrics = github()
    push(github_metrics, prefix="github")
    play_metrics = play()
    push(play_metrics, prefix="play")

    # tC Dev Hour Metrics
    github_token = get_env_var('GITHUB_TOKEN')
    tasks = getJSONfromURL(tasks_api, github_token)
    tasks_metrics = getTaskMetrics(tasks)
    logger.info(tasks_metrics)
    tasks_messages = getGraphiteMessages(tasks_metrics, 'tc_dev')
    pushGraphite(tasks_messages)

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
