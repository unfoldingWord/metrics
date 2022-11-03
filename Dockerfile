FROM python:alpine

WORKDIR /app

COPY gatherer.py .
COPY requirements.txt .
COPY gatherers ./gatherers

# Install requirements
# Disable caching, to keep Docker image lean
RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python", "/app/gatherer.py" ]
