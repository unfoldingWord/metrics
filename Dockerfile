FROM python:alpine

WORKDIR /app

COPY gatherer.py .
COPY requirements.txt .
COPY gatherers ./gatherers
ADD https://truststore.pki.rds.amazonaws.com/us-west-2/us-west-2-bundle.pem ./aws-ssl-certs

# Install requirements
# Disable caching, to keep Docker image lean
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "/app/gatherer.py" ]
