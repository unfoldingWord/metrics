FROM python:alpine

ADD gatherer.py /

RUN pip install requests statsd

CMD [ "python", "./gatherer.py" ]
