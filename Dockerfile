FROM python:alpine

ADD gatherer.py /
ADD template.html /

RUN pip install requests statsd boto3

CMD [ "python", "./gatherer.py" ]
