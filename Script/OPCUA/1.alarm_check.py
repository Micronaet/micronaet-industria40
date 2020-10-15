#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
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
import telepot
import ConfigParser
from opcua_robot import RobotOPCUA

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
cfg_file = os.path.expanduser('./start.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])

# Telegram parameters:
telegram_token = config.get('Telegram', 'token')
telegram_group = config.get('Telegram', 'group')

# Robot parameters:
robot_name = config.get('robot', 'name')

# Load Robot:
robot = RobotOPCUA()
alarm_found = robot.get_alarm_info()
# robot.check_is_alarm()
# robot.check_is_working()
# robot.check_machine()
del(robot)


# Telegram:
bot = telepot.Bot(telegram_token)
bot.getMe()

clean_file = []
print('Check alarm')
for root, folders, files in os.walk(robot_folder):
    for filename in files:
        if filename.startswith(start):
            fullname = os.path.join(root, filename)

            data = {
                'counter': 0,
                'error_code': False,
                'date': False,
                }
            for line in open(fullname, 'r'):
                if line.startswith(date):
                    data['counter'] += 1
                    data['date'] = line.strip().split('=')
                if line.startswith(error_code):
                    data['error_code'] = line.strip().split('=')
                    data['counter'] += 1
                    break
            if data['counter'] == 2:
                event_text = \
                    'Robot: %s\nAllarme: Codice %s\nDescrizione: %s' % (
                        robot_name,
                        data['error'],
                        data['data'],
                        )
                bot.sendMessage(telegram_group, event_text)
                clean_file.append(fullname)
                print(event_text.replate('\n', ' - '))
    break

# Clean alarm used:
if clean_file:
    print('Clean file used')
    for fullname in clean_file:
        print('Removing: %s' % fullname)
        os.remove(fullname)

"""
::AsGlobalPV:Allarmi.N[x].Dati.Attivo            (BOOL)
::AsGlobalPV:AttrezzaturaInLavoro.Nome           (STRING[79])
::AsGlobalPV:Macchina.Stato                      (INTEGER)
::AsGlobalPV:Macchina.Manuale                    (BOOL)
::AsGlobalPV:Macchina.Automatico                 (BOOL)
::AsGlobalPV:OreLavoroUtenza.N[x]                (INTEGER)
"""
