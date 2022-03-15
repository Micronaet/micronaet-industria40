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
config_file = './start.cfg'
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
    robot_present = True
    while robot_present:  # Internal loop:
        last_speed = status['speed']
        for call in calls:
            try:
                call_text = calls[call]
                result = robot.get_data_value(
                    call_text,
                    verbose=False,
                )
                status[call] = result
                print('Chiamata: %s risposta: %s' % (call, result))
                time.sleep(wait['working'])
            except:
                # Robot not present:
                try:
                    print('Robot not responding!')
                    del robot
                    robot_present = False
                except:
                    pass
                break

        # ---------------------------------------------------------------------
        # Alarm check with raise on telegram:
        # ---------------------------------------------------------------------
        error_raised = False
        while not error_raised:
            if last_speed <= 0 and status['speed'] > 0:
                try:
                    bot.sendMessage(
                        telegram_group,
                        u'[INFO] Ripresa nastro trasportatore',
                    )
                    error_raised = True
                except:
                    print('Cannot raise restart operation')
                    time.sleep(wait['telegram'])

            elif last_speed > 0 and status['speed'] <= 0:
                try:
                    bot.sendMessage(
                        telegram_group,
                        u'[ALLARME] Arresto nastro trasportatore!',
                    )
                    error_raised = True
                except:
                    print('Cannot raise stop operation')
                    time.sleep(wait['telegram'])

            else:  # nothing to raise
                error_raised = True

    robot = False
    bot.sendMessage(
        telegram_group,
        u'[WARNING] Disconnessione robot (fine monitoraggio)\n%s' % ('-' * 80),
    )
del robot



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
