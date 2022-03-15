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
import time
from datetime import datetime
import telepot
import erppeek
import pdb

from opcua_robot import RobotOPCUA
try:
    import ConfigParser
except:
    import configparser as ConfigParser

wait = {
    'robot': 1 * 30,  # Test every one minute
    'working': 10,   # Test every 30 seconds
    'telegram': 10,   # Wait for telegram error
}

# -----------------------------------------------------------------------------
# Parameters:
# -----------------------------------------------------------------------------
# A. Telegram:
config_file = './start_working.cfg'
config = ConfigParser.ConfigParser()
config.read([config_file])

telegram_token = config.get(u'Telegram', u'token')
telegram_group = config.get(u'Telegram', u'group')
check_from = config.get('robot', 'check_from')

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
parameter = {
    'temp_grease': 'Termoregolatore sgrassaggio',
    'temp_dry': 'Termoregolatore asciugatura',
    'temp_bake': 'Termoregolatore cottura',
    'speed': u'Velocità trasporto',
}
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
    'speed': 0.1,  # for raise speed 0 first time
    'counter': 0,
    'total': 1000,
}

try:
    while True:
        # -------------------------------------------------------------------------
        # Phase 1: Get robot loop:
        # -------------------------------------------------------------------------
        while not robot:
            try:
                robot = RobotOPCUA()
                bot.sendMessage(
                    telegram_group,
                    u'[INFO] Connessione con robot (inizio controllo lavoro)',
                )
            except:
                # Wait and repeat
                time.sleep(wait['robot'])
                print('Robot non presente!')
                continue

        # -------------------------------------------------------------------------
        # Phase 2: Check working time:
        # -------------------------------------------------------------------------
        while True:  # Internal loop:
            last_speed = status['speed']
            message = '%s Stato forno:\n' % datetime.now()
            for call in calls:
                try:
                    call_text = calls[call]
                    result = robot.get_data_value(
                        call_text,
                        verbose=False,
                    )
                    status[call] = result
                    message += '%s: %s\n' % (
                        parameter.get(call, ''), result)
                except:  # Robot not present:
                    try:
                        print('Robot not responding!')
                        del robot
                        break
                    except:
                        break
            print('%s [counter %s]' % (message, status['counter']))
            time.sleep(wait['working'])

            # ---------------------------------------------------------------------
            # Alarm check with raise on telegram:
            # ---------------------------------------------------------------------
            error_raised = False
            while not error_raised:
                if last_speed <= 0 < status['speed']:
                    try:
                        bot.sendMessage(
                            telegram_group,
                            u'[INFO] Ripresa nastro trasportatore:\n%s' % message,
                        )
                        error_raised = True
                    except:
                        print('Cannot raise restart operation')
                        time.sleep(wait['telegram'])

                elif last_speed > 0 >= status['speed']:
                    try:
                        bot.sendMessage(
                            telegram_group,
                            u'[ALLARME] Arresto nastro trasportatore:\n%s' %
                            message,
                        )
                        error_raised = True
                    except:
                        print('Cannot raise stop operation')
                        time.sleep(wait['telegram'])

                elif status['counter'] <= 0:
                    try:
                        bot.sendMessage(
                            telegram_group,
                            u'[INFO] Messagio periodico stato forno:\n%s' %
                            message,
                        )
                        error_raised = True
                        # Restore counter
                        status['counter'] = status['total']
                    except:
                        print('Cannot raise stop operation')
                        time.sleep(wait['telegram'])

                else:  # nothing to raise
                    status['counter'] -= 1
                    error_raised = True

        robot = False
        bot.sendMessage(
            telegram_group,
            u'[WARNING] Disconnessione robot (fine monitoraggio)\n%s' % ('-' * 80),
        )
finally:
    try:
        print('Disconnessione per programma fermato!')
        del robot
    except:
        pass

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
# todo Test OPCUA variables
# todo Update ODOO if done (add time, duration)
"""
# Parte per test:
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
"""
