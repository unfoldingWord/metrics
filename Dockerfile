FROM cgr.dev/chainguard/wolfi-base

# Set Python version
ARG version=3.12

WORKDIR /app

# Install required packages
RUN apk update && apk add --no-cache \
    python-${version} \
    py${version}-pip \
    py${version}-setuptools

# Copy app files
COPY gatherer.py .
COPY requirements.txt .
COPY gatherers ./gatherers
ADD https://truststore.pki.rds.amazonaws.com/us-west-2/us-west-2-bundle.pem ./aws-ssl-certs/

# Install requirements
# Disable caching, to keep Docker image lean
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "/app/gatherer.py" ]
