import json
import boto3
import logging
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handle(event, context):
    """
    Lambda handler
    """
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
    saveToS3(metrics)

    return event

def getJSONfromURL(url):
    raw = requests.get(url)
    return raw.json()

def saveToS3(content):
    client = boto3.client('s3')
    key = client.put_object(Bucket='api.door43.org',
                            Key='v3/catalog_metrics.json',
                            Body=json.dumps(content),
                            ContentType='application/json')


if __name__ == "__main__":
    logging.basicConfig()
    handle({}, {})
