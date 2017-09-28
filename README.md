# Metrics

## Overview

This is a simple python script that periodically update metrics that we want to track on a [dashboard page](https://dash.door43.org).

## Developer Setup

Make sure you have docker installed.

Build the container with `sudo docker build -t py-metrics .` .

Run the resulting container with `sudo docker run py-metrics`.  The results will be output to console but are also sent to the statsd metric collecting service.
