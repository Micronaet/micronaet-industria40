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

from datetime import datetime, timedelta


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
    call_payload = request.get_json()
    params = call_payload['params']
    command = params['command']
    verbose = params.get('verbose')

    # -------------------------------------------------------------------------
    #                             Execute call:
    # -------------------------------------------------------------------------
    # Start reply payload:
    reply_payload = {
        'success': False,
        'reply': {},
        }
    pdb.set_trace()
    if 'mysql' in params:
        # MySQL call:
        mysql_param = params.get('mysql', {})
    else:
        mysql_param = {}

    # -------------------------------------------------------------------------
    #                       I40 Read statistics:
    # -------------------------------------------------------------------------
    if command == 'ping':
        reply_payload['success'] = True

    elif command == 'mysql_select':
        try:
            connection = mysql.connector.connect(**mysql_param)
            cur = connection.cursor()
            query = params.get('query')
            write_log(
                log_f, 'Executing select query: %s' % query, verbose=verbose)
            cur.execute(query)

            reply_payload['reply']['record'] = []  # Prepare reply
            for row in cur:
                if verbose:
                    print(row)
                clean_row = []
                for field in row:
                    if field is None:
                        clean_row.append(field or '')
                    elif type(field) in (str, int, float, list, tuple, dict):
                        clean_row.append(field)
                    else:
                        clean_row.append(str(field))

                reply_payload['reply']['record'].append(clean_row)
            cur.close()
            connection.close()

            reply_payload['success'] = True
        except:
            reply_payload['reply']['error'] = str(sys.exc_info())

    # -------------------------------------------------------------------------
    #                       I40 Insert Job:
    # -------------------------------------------------------------------------
    elif command == 'mysql_insert':
        # Insert Job on I40 robot:
        try:
            connection = mysql.connector.connect(**mysql_param)
            cur = connection.cursor()

            # INSERT INTO QUERY:
            query = params.get('query')
            write_log(
                log_f, 'Executing insert query: %s' % query, verbose=verbose)
            cur.execute(query)
            connection.commit()
            reply_payload['reply']['id'] = cur.lastrowid
            reply_payload['success'] = True
        except:
            reply_payload['reply']['error'] = str(sys.exc_info())

    # -------------------------------------------------------------------------
    #                       I40 Delete Job:
    # -------------------------------------------------------------------------
    elif command == 'mysql_delete':
        # Insert Job on I40 robot:
        try:
            connection = mysql.connector.connect(**mysql_param)
            cur = connection.cursor()

            # DELETE QUERY:
            query = params.get('query')
            write_log(
                log_f, 'Executing delete query: %s' % query, verbose=verbose)
            cur.execute(query)
            connection.commit()
            reply_payload['success'] = True
        except:
            reply_payload['reply']['error'] = str(sys.exc_info())

    # -------------------------------------------------------------------------
    #                       I40 Unmanaged calls:
    # -------------------------------------------------------------------------
    else:
        # Bad call:
        reply_payload['reply']['error'] = \
            '[ERROR] ODOO is calling wrong command {}\n'.format(command)

    # -------------------------------------------------------------------------
    # Prepare response
    # -------------------------------------------------------------------------
    return reply_payload


@app.route('/')
def hello_geek():
    return '<h1>Hello from Micronaet Industria 4.0 agent</h1>'


if __name__ == "__main__":
    app.run(debug=True, host=host, port=port)
    write_log(log_f, 'End ODOO-I40 Flask agent')
