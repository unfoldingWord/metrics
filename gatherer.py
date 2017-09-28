import json
import logging
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def getJSONfromURL(url):
    raw = requests.get(url)
    return raw.json()

def catalog():
    metrics = {}
    catalog = getJSONfromURL('https://api.door43.org/v3/catalog.json')
    langnames = getJSONfromURL('https://td.unfoldingword.org/exports/langnames.json')

    # Door43-Catalog metrics
    metrics['catalog_total_langs'] = len(catalog['languages'])
    metrics['catalog_obs_langs'] = 0
    metrics['catalog_bible_langs'] = 0
    metrics['catalog_ta_langs'] = 0
    gl_codes = [x['lc'] for x in langnames if x['gw']]
    metrics['catalog_gl_with_content'] = len([x for x in catalog['languages'] if x['identifier'] in gl_codes])
    for x in catalog['languages']:
        for y in x['resources']:
            if y['identifier'] == 'obs':
               metrics['catalog_obs_langs'] += 1 
            elif y['identifier'] == 'ta':
               metrics['catalog_ta_langs'] += 1 
            elif y['identifier'] not in ['obs-tq', 'tw', 'tq', 'tn', 'obs-tn']:
               metrics['catalog_bible_langs'] += 1 

    # tD metrics
    metrics['td_total_langs'] = len(langnames)
    metrics['td_gls'] = len(gl_codes)
    metrics['td_private_use_langs'] = len([x for x in langnames if '-x-' in x['lc']])
    logger.info(metrics)

def github():
    metrics = {}
    release_api = 'https://api.github.com/repos/unfoldingWord-dev/{0}/releases'
    software = ['translationCore', 'ts-android', 'ts-desktop', 'uw-android']
    for x in software:
        metrics['software_{0}'.format(x)] = 0
        releases = getJSONfromURL(release_api.format(x))
        for entry in releases:
            for asset in entry['assets']:
                metrics['software_{0}'.format(x)] += asset['download_count']

    logger.info(metrics)


if __name__ == "__main__":
    logging.basicConfig()
    catalog()
    github()
