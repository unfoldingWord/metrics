FROM python:alpine

ADD gatherer.py /
ADD template.html /

COPY requirements.txt /

# Install requirements
# Disable caching, to keep Docker image lean
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "./gatherer.py" ]
