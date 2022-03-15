 # -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import opcua
import time
import telepot
from opcua import ua
import erppeek
import pdb

from opcua_robot import RobotOPCUA
try:
    import ConfigParser
except:
    import configparser as ConfigParser

wait = {
    'robot': 1 * 30,  # Test every one minute
    'alarm': 10,   # Test every 20 seconds
}

# -----------------------------------------------------------------------------
# Parameters:
# -----------------------------------------------------------------------------
# A. Telegram:
config_file = './start.cfg'
config = ConfigParser.ConfigParser()
config.read([config_file])

telegram_token = config.get(u'Telegram', u'token')
telegram_group = config.get(u'Telegram', u'group')
check_from = config.get('robot', 'check_from')

# -----------------------------------------------------------------------------
# Utility (needed or in class?):
# -----------------------------------------------------------------------------
def get_robot(address, port):
    uri = u'opc.tcp://%s:%s' % (address, port)

    # Create and connect as client:
    robot = opcua.Client(uri)
    try:
        robot.connect()
        return robot
    except:
        return False


def get_data_value(robot, node_description, comment='', verbose=True):
    """ Extract node data
    """
    node = robot.get_node(node_description)
    try:
        data = node.get_data_value().Value._value
    except:
        print('Cannot read: %s, robot unplugged?' % node_description)
        return 'ERROR'
    if verbose:
        comment = comment or node_description
        print(comment, data)
    return data


def set_data_value(robot, node_description, value):
    """ Save node data
    """
    node = robot.get_node(node_description)
    try:
        node.set_value(
            ua.DataValue(ua.Variant(
                value,
                node.get_data_type_as_variant_type()
            )))
    except:
        print('Cannot read: %s, robot unplugged?\n%s' % (
            node_description,
            sys.exc_info(), ))
        return False
    return True


def host_up(host):
    if os.system('ping -c 2 %s' % host) is 0:
        return True
    else:
        return False


# Load Telegram BOT:
bot = telepot.Bot(telegram_token)
bot.getMe()

# Master loop:
robot = False

bot.sendMessage(
    telegram_group,
    u'%s\n[INFO] PC: %s Avvio script controllo funzionamento robot...' % (
        '-' * 80, check_from),
)
calls = {
    'temp_grease': 'ns=3;s="DB_TERMOREG".NR[1].TEMPERATURA',
    'temp_dry': 'ns=3;s="DB_TERMOREG".NR[6].TEMPERATURA',
    'temp_bake': 'ns=3;s="DB_TERMOREG".NR[7].TEMPERATURA',
    'speed': 'ns=3;s="DB_TRAINO".ACT_VEL_TRAINO[1]',
}

status = {
    'working': False,
    'temp_bake': 0.0,
    'temp_grease': 0.0,
    'temp_dry': 0.0,
    'speed': 0.0,
}

while True:
    # -------------------------------------------------------------------------
    # Phase 0: Load telegram in loop?
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Phase 1: Get robot:
    # -------------------------------------------------------------------------
    while not robot:
        try:
            # robot = get_robot('10.10.10.1', 4840)
            robot = RobotOPCUA()
            bot.sendMessage(
                telegram_group,
                u'[INFO] Connessione con robot (inizio controllo lavoro)',
            )
        except:
            # Wait and repeat
            time.sleep(wait['robot'])
            continue

    # -------------------------------------------------------------------------
    # Phase 2: Check working time:
    # -------------------------------------------------------------------------
    try:
        for call in calls:
            print('\nChiamata %s' % call)
            call_text = calls[call]
            result = robot.get_data_value(
                robot,
                call_text,
                verbose=False,
            )
            print('Risposta: %s' % result)

        # Loop:
        robot.alert_alarm_on_telegram(seconds=wait['alarm'], verbose_every=0)
        # if return restart with new robot
    except:
        pass

    try:
        del robot
    except:
        pass

    robot = False
    bot.sendMessage(
        telegram_group,
        u'[WARNING] Disconnessione robot (fine monitoraggio)\n%s' % ('-' * 80),
    )

# robot.check_is_alarm()
# robot.check_is_working()
# robot.check_machine()
del robot



# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
# todo Test OPCUA variables
# todo Update ODOO if done (add time, duration)
pdb.set_trace()
robot = get_robot('10.10.10.1', 4840)
calls = {
    'temp_grease': 'ns=3;s="DB_TERMOREG".NR[1].TEMPERATURA',
    'temp_dry': 'ns=3;s="DB_TERMOREG".NR[6].TEMPERATURA',
    'temp_bake': 'ns=3;s="DB_TERMOREG".NR[7].TEMPERATURA',
    'speed': 'ns=3;s="DB_TRAINO".ACT_VEL_TRAINO[1]',
    }


for call in calls:
    print('\nChiamata %s' % call)
    call_text = calls[call]
    result = get_data_value(
        robot,
        call_text,
        verbose=False,
    )
    print('Risposta: %s' % result)
robot.disconnect()
