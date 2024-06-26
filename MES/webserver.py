#!/usr/bin/python
###############################################################################
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush
#            https://it.linkedin.com/in/thebrush
#            https://linktr.ee/nicolariolini
###############################################################################
import base64
import os
import sys
import pdb
import time
from datetime import datetime, timedelta
import erppeek
from datetime import datetime
from flask import Flask, render_template  # request,
try:
    import configparser as ConfigParser
except:
    import ConfigParser

try:
    from pytz import timezone
except:
    print('Error importing pytz')

# -----------------------------------------------------------------------------
# End point definition:
# -----------------------------------------------------------------------------
app = Flask(
    __name__,
    # template_folder='../templates',
)

# -----------------------------------------------------------------------------
# Read parameters from file:
# -----------------------------------------------------------------------------
current_path = os.path.dirname(__file__)
cfg_file = '~/connection/odoo.cfg'
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
        'refresh': 20,  # Keep in config file?
        },
    }

# -----------------------------------------------------------------------------
# Context for web:
# -----------------------------------------------------------------------------
context_parameters = {}


# -----------------------------------------------------------------------------
# Utility:
# -----------------------------------------------------------------------------
def get_tz_time():
    """ Get Now timezone in Europe Rome
    """
    # utc_time = datetime.now()
    # print(utc_time.strftime('%Y-%m-%d_%H-%M-%S'))
    try:
        europe = timezone('Europe/Rome')
        tz_time = datetime.now(europe)
        return tz_time  # print(tz_time.strftime('%Y-%m-%d_%H-%M-%S'))
    except:
        return 'ERROR'

# Parameters
gmt_gap = 2  # 2 legal hour, 1 solar hour

def parser_write_hour(value, gap=gmt_gap):
    """ Write hour in correct format
    """
    value = str(value or '')
    if not value:
        return ''
    today = str(datetime.now())[:10]
    yesterday = str(datetime.now() - timedelta(hours=24))[:10]
    if value.startswith(today):
        mask = '%H:%M:%S [OGGI]'
    elif value.startswith(yesterday):
        mask = '%H:%M:%S [IERI]'
    else:
        mask = '%H:%M:%S %d/%m/%Y'

    try:
        dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        if gmt_gap:
            italian_dt = dt + timedelta(hours=gap)
        else:
            italian_dt = dt

    except:
        print(f'Error converting {value}')
        return ''
    return italian_dt.strftime(mask)


def auto_refresh_setup():
    """ Set parameters
    """
    if not context_parameters.get('refresh'):
        context_parameters.update({
            'refresh': parameters['webserver']['refresh'],
            'last_refresh': str(datetime.now())[:19],
        })
    # context_parameters['last_update'] = str(datetime.now())[:19]
    context_parameters['last_update'] = str(get_tz_time())[:19]


def generate_robot_static_img():
    """ Load images from ODOO
    """
    # -------------------------------------------------------------------------
    #                             Load data from ODOO:
    # -------------------------------------------------------------------------
    try:
        root_folder = './static/img'
        robot_pool = get_odoo_table(parameters, 'mrp.robot')
        robot_ids = robot_pool.search([])
        robots = robot_pool.browse(robot_ids)
        for robot in robots:
            image = robot.image
            image_fullname = os.path.join(
                root_folder, '{}.jpg'.format(robot.id))

            image_file = open(image_fullname, 'wb')
            image_file.write(base64.decodebytes(bytes(image, 'utf-8')))
            image_file.close()
            print('Updated image {}'.format(image_fullname))
        print('Static image, loaded!')
        return True
    except:
        print('No image, problem loading!')
        return False


rgb_color = {  # For background
    'green': '#c6f9bd',  # b3fcb9
    'yellow': '#f4f9c5',
    'red': '#fcc7c7',
    'darkred': '#ea4b50',
    'black': '#ecedea',
    'grey': '#dbdbdb',
    'darkgrey': '#939393',
    'blue': '#a2bcf9',
}

div_order = {
    'alarm': 1,
    'damage': 1,

    'pause': 2,
    'prepare': 2,
    'working': 3,
    'on': 3,
    'off': 4,
}

colors = {
    'damage': 'darkred',
    'alarm': 'red',
    'prepare': 'blue',
    'pause': 'yellow',
    'working': 'green',
    'on': 'grey',
    'off': 'black',
}


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


@app.route('/')  # , methods=['GET']
def home():
    """ MES Dashboard
    """
    auto_refresh_setup()
    return render_template('home.html', args=context_parameters)


@app.route('/about/')
def about():
    """ About page
    """
    auto_refresh_setup()
    return render_template('about.html', args=context_parameters)


@app.route('/mes/', methods=['GET'])
def mes():
    """ MES Dashboard
    """
    auto_refresh_setup()

    # -------------------------------------------------------------------------
    #                             Load data from ODOO:
    # -------------------------------------------------------------------------
    try:
        robot_pool = get_odoo_table(parameters, 'mrp.robot')

        # ---------------------------------------------------------------------
        # ERP ON:
        # ---------------------------------------------------------------------
        robot_ids = robot_pool.search([])
        div_boxes = []

        robots = sorted(
            robot_pool.browse(robot_ids),
            key=lambda r: div_order.get(r.get_robot_activity_state(), 0))
        last_color = ''
        for robot in robots:
            # Linked robot is used for check state and last change:
            if robot.linked_robot_id:
                check_robot = robot.linked_robot_id  # Parent robot
            else:
                check_robot = robot

            state = check_robot.get_robot_activity_state()
            current_color = div_order.get(state)
            if not last_color:
                last_color = current_color

            # New line:
            if last_color != current_color:
                last_color = current_color
                div_boxes.append('')

            job = robot.current_job_id
            if job:
                job_name = job.name
            else:
                job_name = '[NON PRESENTE]'

            # Change state also depend on last activity
            # if robot.opcua_id and robot.opcua_id.working_command_id:
            last_change = ''
            try:
                # Last change get from linked robot if present:
                if check_robot.opcua_id:
                    last_change = parser_write_hour(
                        check_robot.opcua_id.last_activity_datetime) or \
                        '[NON TROVATA]'
                elif check_robot.mysql_id:
                    last_change = parser_write_hour(
                        check_robot.mysql_id.last_activity_datetime) or \
                        '[NON TROVATA]'
                elif check_robot.ftp_id and check_robot.ftp_id.mode != 'ftp':
                    # FTP in all or fs mode only:
                    last_change = parser_write_hour(
                        check_robot.ftp_id.last_activity_datetime) or \
                        '[NON TROVATA]'
                else:
                    last_change = '[NON RILEVABILE]'
            except:
                pass

            # -----------------------------------------------------------------
            #                        Robot state (all are written):
            # -----------------------------------------------------------------
            # Network:
            robot_state = '{} [{}]'.format(
                robot.name,
                robot.host_ip or '',
            )
            # OPCUA:
            if robot.opcua_id and robot.opcua_state:
                robot_state += '<br/>Stato OPCUA:<br/> {}'.format(
                    robot.opcua_state)
            # MYSQL:
            if robot.mysql_id and robot.mysql_state:
                robot_state += '<br/>Stato SQL:<br/> {}'.format(
                    robot.mysql_state)
            # FTP:
            if robot.ftp_id and robot.ftp_id.mode != 'ftp' and \
                    robot.ftp_state:
                robot_state += '<br/>Stato FTP:<br/> {}'.format(
                    robot.ftp_state)

            div_boxes.append({
                'robot': robot,
                'color': colors.get(state, 'grey'),
                'state': state,
                'last_activity': last_change,
                'job': job_name,
                'robot_state': robot_state,
                })

        div_boxes.append('')  # Necessary for box dimension
    except:
        # ---------------------------------------------------------------------
        # ERP OFF:
        # ---------------------------------------------------------------------
        return render_template(
            'no_ERP.html', args=context_parameters, error=str(sys.exc_info()))

    return render_template(
        'mes.html', args=context_parameters,
        div_boxes=div_boxes,
        parser_write_hour=parser_write_hour,
        # robot=robot,
    )


# Old link keep for back-compatibility:
@app.route('/odoo/industria/mes/', methods=['GET'])
def mes_online():
    """ MES Dashboard
    """
    return mes()


if __name__ == '__main__':
    # app.secret_key = b'MICRONAET_SUPER_SECRET_KEY'
    # app.config['SESSION_TYPE'] = 'filesystem'
    # this_session.init_app(app)

    # Start up:
    generate_robot_static_img()

    # Webserver load:
    app.run(
        debug=parameters['webserver']['debug'],
        host=parameters['webserver']['host'],
        port=parameters['webserver']['port'],
        )
