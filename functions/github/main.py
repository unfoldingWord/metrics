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
    release_api = 'https://api.github.com/repos/unfoldingWord-dev/{0}/releases'
    software = ['translationCore', 'ts-android', 'ts-desktop', 'uw-android']
    for x in software:
        metrics['software_{0}'.format(x)] = 0
        releases = getJSONfromURL(release_api.format(x))
        for entry in releases:
            for asset in entry['assets']:
                metrics['software_{0}'.format(x)] += asset['download_count']

    logger.info(metrics)
    saveToS3(metrics)

    return event

def getJSONfromURL(url):
    raw = requests.get(url)
    return raw.json()

def saveToS3(content):
    client = boto3.client('s3')
    key = client.put_object(Bucket='api.door43.org',
                            Key='v3/github_metrics.json',
                            Body=json.dumps(content),
                            ContentType='application/json')


if __name__ == "__main__":
    logging.basicConfig()
    handle({}, {})
