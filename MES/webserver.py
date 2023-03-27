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
rgb_color = {  # For background
    'green': '#c6f9bd',  # b3fcb9
    'yellow': '#f4f9c5',
    'red': '#fcc7c7',
    'black': '#ecedea',
    'grey': '#dbdbdb',
    'darkgrey': '#939393',
    'blue': '#a2bcf9',
}


# HTML Utility:
def html_td(value, bgcolor='white', tag='td', align='left', bold=False):
    """ Format TD cell
    """
    bgcolor = rgb_color.get(bgcolor, bgcolor)
    if bold:
        strong1 = '<strong>'
        strong2 = '</strong>'
    else:
        strong1 = strong2 = ''

    return '<%s bgcolor="%s" align="%s" ' \
           'style="border: 1px solid black">%s%s%s</%s>' % (
               tag, bgcolor, align,
               strong1, value, strong2,
               tag)


def html_font(
        text, font='Courier, Verdana, Lucida Console', color='black',
        size=2):
    """ Setup font
    """
    return '<font size="%s" face="%s" color="%s">%s</font>' % (
        size,
        font,
        color,
        text,
    )


def html_tag(text, tag='div', bgcolor='white', bold=False, border=False):
    """ Setup P or other tags
    """
    bgcolor = rgb_color.get(bgcolor, bgcolor)
    if bold:
        bold1 = '<strong>'
        bold2 = '</strong>'
    else:
        bold1 = bold2 = ''

    if border:
        border = 'border: 1px solid black;'
    else:
        border = ''

    return '<%s style="background: %s;%s">%s%s%s</%s>' % (
        tag, bgcolor, border,
        bold1, text, bold2,
        tag,
    )


# Test
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


@app.route('/', methods=['GET'])
def ODOOIndustriaHello():
    """ MES Dashboard
    """
    return '''
        <html>
            <header>
                <title>Industria 4.0 Web server</title>
                <meta http-equiv="refresh" content="%s">
            </header>
            <body>
                <p>
                    <b>Micronaet</b><br/>
                    Per vedere lo stato utilizzare: /odoo/industria/mes
                </p>
            </body>
        </html>
        '''


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
    category_robot = {}
    for robot in robot_pool.browse(robot_ids):
        category = robot.category_id
        if category not in category_robot:
            category_robot[category] = []
        category_robot[category].append(robot)

    # Header:
    lines = []
    header_line = ''
    for category in category_robot:
        header_line = '<th></th>' % category.name
    lines.append('<tr>%s</tr>' % header_line)
    table = '<table width="100%%">%s</table>' % (''.join(lines))

    for category in category_robot:
        for robot in category_robot[category]:

            job = robot.current_job_id
            if job:
                job_name = job.name
            else:
                job_name = '/'
            robot_detail += \
                '<b>{}</b>: Stato <b>{}</b> Ultima attivit&agrave;: {} Job: {}' \
                '<br/>'.format(
                    robot.name,
                    robot.state,
                    robot.last_log_id,
                    job_name,
                )

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
    # return table + html
    return html


app.run(
    debug=parameters['webserver']['debug'],
    host=parameters['webserver']['host'],
    port=parameters['webserver']['port'],
    )

