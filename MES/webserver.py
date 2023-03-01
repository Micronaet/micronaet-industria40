#!/usr/bin/python
###############################################################################
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush
#            https://it.linkedin.com/in/thebrush
#            https://linktr.ee/nicolariolini
###############################################################################

import os
import sys
import pdb
import time
import erppeek
from flask import Flask, request
from datetime import datetime
try:
    import configparser as ConfigParser
except:
    import ConfigParser


# -----------------------------------------------------------------------------
# End point definition:
# -----------------------------------------------------------------------------
app = Flask(__name__)

# -----------------------------------------------------------------------------
# Read parameters from file:
# -----------------------------------------------------------------------------
current_path = os.path.dirname(__file__)

cfg_file = os.path.join(current_path, 'odoo.cfg')
cfg_file = os.path.expanduser(cfg_file)
if not os.path.isfile(cfg_file):
    print('Config file not present!')
    sys.exit()

config = ConfigParser.ConfigParser()
config.read([cfg_file])

# -------------------------------------------------------------------------
# Connect to ODOO:
# -------------------------------------------------------------------------
parameters = {
    'odoo': {
        'server': config.get('odoo', 'server'),
        'port': config.get('odoo', 'port'),
        'username': config.get('odoo', 'username'),
        'password': config.get('odoo', 'password'),
        'database': config.get('odoo', 'database'),
        'handle': False,
        },

    'webserver': {
        'host': '0.0.0.0',
        'port': 8080,
        'debug': True,
        'refresh': 5,
        },
    }


# -----------------------------------------------------------------------------
# Utility:
# -----------------------------------------------------------------------------
def get_odoo_table(param, table='mrp.robot'):
    """ Return ODOO if not working
    """
    if False:
        pass
        # todo test if works and return it
    else:
        param['odoo']['handle'] = erppeek.Client(
            'http://%s:%s' % (
                param['odoo']['server'],
                param['odoo']['port']),
            db=param['odoo']['database'],
            user=param['odoo']['username'],
            password=param['odoo']['password'],
            )
    return param['odoo']['handle'].model(table)


@app.route('/odoo/industria/mes', methods=['GET'])
def ODOOIndustriaStatus():
    """ MES Dashboard
    """
    try:
        robot_pool = get_odoo_table(parameters, 'mrp.robot')
        erp_on = True
    except:
        erp_on = False

    # -------------------------------------------------------------------------
    # ERP OFF:
    # -------------------------------------------------------------------------
    if not erp_on:
        html = '''
            <html>
                <header>
                    <title>Industria 4.0 Web server</title>
                    <meta http-equiv="refresh" content="%s">
                </header>
                <body>
                    <p>
                        <b>Micronaet</b><br/>
                        ODOO non operativo, attesa risposta...\n<br/>Now: %s
                    </p>
                </body>''' % (
                parameters['webserver']['refresh'],
                str(datetime.now())[:19],
                )

        return html

    # -------------------------------------------------------------------------
    # ERP ON:
    # -------------------------------------------------------------------------
    robot_ids = robot_pool.search([])
    robot_detail = ''
    for robot in robot_pool.browse(robot_ids):
        robot_detail += '%s<br/>' % robot.name

    html = '''
        <html>
            <header>
                <title>Industria 4.0 Web server</title>
                <meta http-equiv="refresh" content="%s">
            </header>
            <body>
                <p>
                    <b>Micronaet</b><br/>
                    Flask Webserver for OpenERP - Mexal call\n<br/>Now: %s<br/>
                    %s
                </p>
            </body>''' % (
        parameters['webserver']['refresh'],
        str(datetime.now())[:19],
        robot_detail,
        )
    return html


app.run(
    debug=parameters['webserver']['debug'],
    host=parameters['webserver']['host'],
    port=parameters['webserver']['port'],
    )

