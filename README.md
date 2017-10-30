# Metrics

## Overview

This is a simple python script that periodically update metrics that we want to track on a [dashboard page](https://dash.door43.org).

## Developer Setup

Make sure you have docker installed.

Build the container with `sudo docker build -t py-metrics .` .

Run the resulting container with `sudo docker run --rm -e "GITHUB_TOKEN=Your_Token" py-metrics`.

When running on the server, use `sudo docker run --rm -e "GITHUB_TOKEN=Your_Token" --net="host" py-metrics` so that the app has access to the statsd server.
