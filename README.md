# Metrics

## Overview

These are apex functions that periodically update metrics that we want to track on a [dashboard page](https://freeboard.io/board/VNPPXV).

## Developer Setup

First, make sure you have apex installed, instructions at [apex.run](http://apex.run).  After that you may use the normal apex commands to interact with these functions.

The functions are given necessary write permission to S3 via the IAM role that they run as.

### Local Setup

The functions can be run locally, provided that you have sufficient AWS credentials configured for your user account (Boto3 will automatically read from ~/.aws/credentials).

Setup requirements like this:

    pip install virtualenv
    virtualenv venv
    pip install -r functions/catalog/main.py
    pip install -r functions/github/main.py


### Testing Locally

You can now run the functions locally, like so:

    python functions/catalog/main.py
    python functions/github/main.py
