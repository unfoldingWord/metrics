import os
import re
import sys
import json
import boto3
import socket
import statsd
import logging
import requests
import datetime
import urllib.request
import time
import io
import requests
import zipfile
import pprint  # dump an object, test only.

logger = logging.getLogger()
logger.setLevel(logging.INFO)

devs = [ ('bspidel', 3),
         ('klappy', 0),
         ('RoyalSix', 6),
         ('mannycolon', 6),
         ('richmahn', 5),
         ('PhotoNomad0', 5)
       ]
api_status = { 'complete': 0,
               'in-progress': 1,
               'incomplete': 1,
               'error': 2,
             }
cols = { '12+ Months': 'one',
         '6 Months': 'two',
         '3 Months': 'three',
         '1 Month': 'four',
       }
dsm_board_pos = { 'G0WhbXlL': 'one',
                  'sA1QqK2i': 'two',
                  'RAaZkiFR': 'three',
                  'eB7kaK2E': 'four',
                  'hCY5TVfN': 'five',
                  'I41yr39N': 'six',
                  'B7SE15xE': 'seven'
                }
milestones_api = "https://api.github.com/repos/unfoldingWord-dev/translationCore/milestones"
issues_api     = "https://api.github.com/repos/unfoldingWord-dev/translationCore/issues?milestone={0}"
tasks_api      = "https://api.github.com/repos/unfoldingWord-dev/translationCore/issues?labels=Task&page={0}"
zenhub_api     = "https://api.zenhub.io/p1/repositories/65028237/board?access_token={0}"
sendgrid_api   = "https://api.sendgrid.com/v3/stats?start_date={0}"
d43api_api     = "https://api.door43.org/v3/lambda/status"
trello_api     = "https://api.trello.com/1/boards/{0}"
catalog_api    = "https://api.door43.org/v3/catalog.json"

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

def getJSONfromURL(url, token="", auth="", params=""):
    if token:
        raw = requests.get(url, auth=('token', token))
    elif auth:
        raw = requests.get(url, headers={'Authorization': auth})
    elif params:
        raw = requests.get(url, params=params)
    else:
        raw = requests.get(url)
    return raw.json()

def push(metrics, host='dash.door43.org', port=8125, prefix=''):
    stats = statsd.StatsClient(host, port, prefix=prefix)
    for k,v in metrics.items():
        stats.gauge(k, v)

def pushGraphite(messages, host='dash.door43.org', port=2003):
    for m in messages:
        sock = socket.socket()
        sock.connect((host, port))
        sock.sendall(m.encode('utf-8'))
        sock.close()

def getAlignmentCounts(lc, cdnPath):
    # Receive language name and cdn path to zip file for language
    # Return list of projects with numbers of alignments
    counts = {}
    if cdnPath.count('.zip') > 0:
        #logger.info(' getAlignmentCounts: lc: ' + lc + ' cdnPath: ' + cdnPath)
        response = requests.get(cdnPath)
        with zipfile.ZipFile(io.BytesIO(response.content)) as theZip:
            for zipInfo in theZip.infolist():
                filename = zipInfo.filename
                #logger.info(' getAlignmentCounts: filename: ' + filename )
                if filename.count('.usfm') > 0:
                    with theZip.open(zipInfo) as theFile:
                        book = str(filename)[-8 : -5].lower()
                        slug = lc + '_' + book
                        theText = str(theFile.read())
                        count = theText.count('\\zaln-s')
                        if count > 0:
                            counts[slug] = count
                            #logger.info(' getAlignmentCounts: filename: ' + filename + ' counts[' + slug + ']: ' + str(counts[slug]))
    return counts

def catalog(gl_codes, metrics={}):
    catalog = getJSONfromURL(catalog_api)
    metrics['total_langs'] = len(catalog['languages'])
    metrics['gls_with_content'] = len([x for x in catalog['languages'] if x['identifier'] in gl_codes])
    all_resources = 0
    all_bpfs = 0
    startTime = time.time()
    for x in catalog['languages']:
        for y in x['resources']:
            all_resources += 1
            # Resources by identifier
            if not 'resources_{}_langs'.format(y['identifier']) in metrics:
                metrics['resources_{}_langs'.format(y['identifier'])] =0
            metrics['resources_{}_langs'.format(y['identifier'])] +=1
            # Resources by subject
            if not 'subject_{}'.format(y['subject']) in metrics:
                metrics['subject_{}'.format(y['subject'])] =0
            metrics['subject_{}'.format(y['subject'])] +=1
    metrics['all_resources'] = all_resources
    #logger.info( ' resources: ' + str(all_resources))
    isTa = False
    isTn = False
    isTq = False
    isTw = False    
    counts = {}
    for lang in catalog['languages']:                # look at all the languages
        lc = lang['identifier']
        #logger.info( ' catalog: lc: ' + lc )
        for res in lang['resources']:
            resource = res['identifier']
            subject = res['subject']
            #logger.info( '   catalog: resource: ' + resource )
            if subject == 'Aligned Bible':
                for fmt in res['formats']:
                    cdnPath = fmt['url']
                    updateCounts = getAlignmentCounts(lc, cdnPath)
                    #logger.info( '     catalog: lc: ' + lc + ', resource: ' + resource + ' books w/ alignment: ' + str(len(updateCounts)))
                    if len(updateCounts) > 0:
                        counts.update(updateCounts)
            elif resource == 'ta':
                #logger.info( ' catalog: Found ta for: ' + lc)
                isTa = True
            elif resource == 'tn':
                #logger.info( ' catalog: Found tn for: ' + lc)
                isTn = True
            elif resource == 'tq':
                #logger.info( ' catalog: Found tq for: ' + lc)  
                isTq = True
            elif resource == 'tw':  
                #logger.info( ' catalog: Found tw for: ' + lc)
                isTw = True
        # end of language
        if isTa and isTn and isTq and isTw:   
            #previousBpfs = all_bpfs
            #logger.info(' catalog: got all resources for: ' + lc)   
            for key in counts:
                if key.find(lc) == 0:
                    #logger.info(' catalog: key: ' + key)
                    if counts[key] > 0:        
                        all_bpfs += 1    
                        #logger.info(' catalog: Found BP for: ' + key)  
            #logger.info( ' catalog added: ' + str(all_bpfs - previousBpfs) + ' BPs')
        isTa = False
        isTn = False
        isTq = False
        isTw = False    
    logger.info( ' catalog: Elapsed time: ' + str(time.time() - startTime) + ' seconds')                                               
    metrics['all_bpfs'] = all_bpfs
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
    pp = pprint.PrettyPrinter()
    print('      milestone_json: ')
    pp.pprint(milestone_json)
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

def getDSMBoards(tparams, dsm_boards):
    # Returns a dictionary of the card data in the boards
    trello_data = {}
    for board in dsm_boards:
        trello_data[board] = getJSONfromURL(trello_api.format(board) + '/lists', params=tparams)
    return trello_data

def getBoardNames(tparams, boards):
    tparams['fields'] = 'name'
    board_names = {}
    for b in boards:
        r = getJSONfromURL(trello_api.format(b), params=tparams)
        board_names[b] = r['name']
    return board_names

def trelloAllHtml(boards, board_names):
    html_data = []
    for b in boards.keys():
        html_data.append('<h2>#{0}</h2>'.format(board_names[b]))
        html_data.append('<div class="row">')
        for lane in boards[b]:
            if lane['name'] not in cols: continue
            html_data.append('  <div class="{0}"><h3>{1}</h3>'.format(
                                                 cols[lane['name']], lane['name']))
            for card in lane['cards']:
                html_data.append('    <blockquote class="trello-card-compact">')
                html_data.append('      <a href="{0}">Card</a>'.format(card['shortUrl']))
                html_data.append('    </blockquote>')
            html_data.append('  </div>')
        html_data.append('</div>')
        html_data.append('<hr>')
    html_data.pop()
    return html_data

def trelloCols(boards, col, board_names):
    html_data = []
    html_data.append('<h2>DSM OKRs: {0}</h2>'.format(col))
    html_data.append('<div class="row">')
    for b in board_names.keys():
        for lane in boards[b]:
            if lane['name'] != col: continue
            html_data.append('  <div class="{0}"><h3>{1}</h3>'.format(
                                            dsm_board_pos[b], board_names[b]))
            for card in lane['cards']:
                html_data.append('    <blockquote class="trello-card-compact">')
                html_data.append('      <a href="{0}">Card</a>'.format(card['shortUrl']))
                html_data.append('    </blockquote>')
            html_data.append('  </div>')
    html_data.append('</div>')
    #html_data.pop()
    return html_data

def trelloUpload(html, dest):
    s3 = boto3.resource('s3', 'us-west-2')
    dest += '/index.html'
    html_str = '\n'.join(html)
    output = open('template.html', 'rb').read()
    output += html_str.encode('utf-8')
    output += b'\n</body>\n</html>'
    s3.Bucket('trello.door43.org').put_object(
                         Body=output,
                         ContentType='text/html',
                         CacheControl='max-age=60',
                         Key=dest)

if __name__ == "__main__":
    logging.basicConfig()
    status = getJSONfromURL(d43api_api)
    status_metrics = d43api(status)
    push(status_metrics, prefix="door43_api")
    td_metrics, gl_codes = tD()
    push(td_metrics, prefix="td")
    catalog_metrics = catalog(gl_codes)
    push(catalog_metrics, prefix="door43_catalog")
    # Only get these periodically (helps stay under rate limit)
    if (datetime.datetime.now().minute == 0 and 
              datetime.datetime.now().hour in [8, 12, 16, 20]):
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
    if type(sendgrid_stats) == list:
        sendgrid_metrics = sendgrid_stats[0]['stats'][0]['metrics']
        logger.info(sendgrid_metrics)
        push(sendgrid_metrics, prefix="sendgrid")

    # Trello stats
    tparams = {'cards': 'open'}
    tparams['key'] = get_env_var('TRELLO_KEY')
    tparams['token'] = get_env_var('TRELLO_SECRET')
    dsm_boards = ['G0WhbXlL', 'sA1QqK2i', 'RAaZkiFR', 'eB7kaK2E', 'hCY5TVfN', 'I41yr39N', 'B7SE15xE']
    board_names = getBoardNames(tparams, dsm_boards)
    board_data = getDSMBoards(tparams, dsm_boards)
    html = trelloAllHtml(board_data, board_names)
    trelloUpload(html, 'okrs')
    for col in cols:
        html = trelloCols(board_data, col, board_names)
        directory = 'okrs/{0}'.format(col.replace(' ', '_').replace('+', '_'))
        trelloUpload(html, directory)

# Retired tests
#import pprint  # dump an object, test only.
#pp = pprint.PrettyPrinter()
#print('       ' + lc + ': ')
#pp.pprint(counts)
#myPrint('counts', counts)
