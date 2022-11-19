#!/usr/bin/python
###############################################################################
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush
#            https://it.linkedin.com/in/thebrush
#            https://linktr.ee/nicolariolini
###############################################################################

import os
import pdb
import sys

from flask import Flask, request
import mysql.connector

from datetime import datetime


try:
    import ConfigParser
except:
    pass
try:
    import configparser as ConfigParser
except:
    pass


# -----------------------------------------------------------------------------
# Utility:
# -----------------------------------------------------------------------------
def write_log(log_f, message, mode='INFO', verbose=True):
    """ Write log file
    """
    complete_message = '%s [%s]: %s' % (
        str(datetime.now())[:19],
        mode,
        message,
    )
    if verbose:
        print(' * {}'.format(complete_message))
    log_f.write('{}\n'.format(complete_message))
    log_f.flush()


# -----------------------------------------------------------------------------
# Read configuration parameter from external file:
# -----------------------------------------------------------------------------
current_path = os.path.dirname(__file__)
log_file = os.path.join(current_path, 'flask.log')
log_f = open(log_file, 'a')
write_log(log_f, 'Start ODOO-Mexal Flask agent')
write_log(log_f, 'Flask log file: {}'.format(log_file))

config_files = [
    os.path.join(current_path, 'flask.cfg'),
]
for config_file in config_files:
    if not os.path.isfile(config_file):
        continue
    cfg_file = os.path.expanduser(config_file)

    config = ConfigParser.ConfigParser()
    config.read([cfg_file])
    host = config.get('flask', 'host')
    port = config.get('flask', 'port')
    write_log(log_f, 'Read config file: {}'.format(config_file))
    break
else:
    write_log(log_f, 'Read default parameter [0.0.0.0:5000]')
    host = '0.0.0.0'
    port = '5000'

# -----------------------------------------------------------------------------
# End point definition:
# -----------------------------------------------------------------------------
app = Flask(__name__)


@app.route('/API/v1.0/micronaet/launcher', methods=['POST'])
def ODOOCall():
    """ Master function for Micronaet Call

    """
    # -------------------------------------------------------------------------
    # Get parameters from call:
    # -------------------------------------------------------------------------
    params = request.get_json()
    rpc_call = params['params']

    command = rpc_call['command']
    parameter = rpc_call['parameters']

    # -------------------------------------------------------------------------
    #                             Execute call:
    # -------------------------------------------------------------------------
    # Start reply payload:
    payload = {
        'success': False,
        'reply': {},
    }

    if 'mysql' in parameter:
        # MySQL call:
        mysql_param = parameter.get('mysql', {})
    else:
        mysql_param = {}

    # -------------------------------------------------------------------------
    #                       I40 Read statistics:
    # -------------------------------------------------------------------------
    if command == 'statistic':
        try:
            connection = mysql.connector.connect(**mysql_param)
            cur = connection.cursor()
            cur.execute('SELECT * FROM %s;' % mysql_param.get('table'))

            payload['reply']['record'] = []  # Prepare reply
            for row in cur:
                payload['reply']['record'].append(row)
            cur.close()
            connection.close()

            payload['success'] = True
        except:
            payload['reply']['error'] = str(sys.exc_info())

    # -------------------------------------------------------------------------
    #                       I40 Insert Job:
    # -------------------------------------------------------------------------
    elif command == 'job':
        # Insert Job on I40 robot:
        try:
            connection = mysql.connector.connect(**mysql_param)
            cur = connection.cursor()

            # INSERT INTO QUERY:
            query = parameter.get('query')
            write_log(log_f, 'Executing query: %s' % query)
            cur.execute(query)

            payload['success'] = True
        except:
            payload['reply']['error'] = str(sys.exc_info())

    # -------------------------------------------------------------------------
    #                       I40 Unmanaged calls:
    # -------------------------------------------------------------------------
    else:
        # Bad call:
        payload['reply']['error'] = \
            '[ERROR] ODOO is calling wrong command {}\n'.format(command)

    # -------------------------------------------------------------------------
    # Prepare response
    # -------------------------------------------------------------------------
    return payload


@app.route('/')
def hello_geek():
    return '<h1>Hello from Micronaet Indutria 4.0 agent</h1>'


if __name__ == "__main__":
    app.run(debug=True, host=host, port=port)
    write_log(log_f, 'End ODOO-I40 Flask agent')
