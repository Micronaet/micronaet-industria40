#!/usr/bin/python
###############################################################################
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush
#            https://it.linkedin.com/in/thebrush
#            https://linktr.ee/nicolariolini
###############################################################################

import os
import pdb
import requests
import json

# -----------------------------------------------------------------------------
# Authenticate to get Session ID:
# -----------------------------------------------------------------------------
url = 'http://localhost:5000/API/v1.0/micronaet/launcher'
headers = {
    'content-type': 'application/json',
}
payload = {
    'jsonrpc': '2.0',
    'params': {
        'command': 'statistic',
        'parameters': {
            'mysql': {
                'host': '192.168.1.1',
                'port': 3306,
                'user': 'user',
                'password': '',
                'database': '',
                'use_pure': False,
                },
            },
        },
    }

response = requests.post(url, headers=headers, data=json.dumps(payload))
response_json = response.json()
if response_json['success']:
    print(response_json)
