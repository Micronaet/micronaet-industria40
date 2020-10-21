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

import pdb
import time
import telepot
from datetime import datetime
from opcua_robot import RobotOPCUA
try:
    import ConfigParser
except:
    import configparser as ConfigParser

# -----------------------------------------------------------------------------
# Parameters:
# -----------------------------------------------------------------------------
# A. Telegram:
config_file = './start.cfg'
config = ConfigParser.ConfigParser()
config.read([config_file])

telegram_token = config.get(u'Telegram', u'token')
telegram_group = config.get(u'Telegram', u'group')

# -----------------------------------------------------------------------------
# Load robot if present:
# -----------------------------------------------------------------------------
seconds = 60 * 5  # minutes check loop
robot = False
previous_status = False
bot = telepot.Bot(telegram_token)
bot.getMe()
while not robot:
    try:
        robot = RobotOPCUA()
        previous_status = 'ON'
        bot.sendMessage(
            telegram_group,
            u'[INFO] Robot alarm check loop ON')
    except:
        print('%s. Robot not present' % datetime.now())
        if previous_status != 'OFF':
            bot.sendMessage(
                telegram_group,
                u'[ERR] Robot alarm check loop OFF')
            previous_status = 'OFF'
    time.sleep(seconds)


robot.alert_alarm_on_telegram()
# robot.check_is_alarm()
# robot.check_is_working()
# robot.check_machine()
del robot

"""
::AsGlobalPV:Allarmi.N[x].Dati.Attivo            (BOOL)
::AsGlobalPV:AttrezzaturaInLavoro.Nome           (STRING[79])
::AsGlobalPV:Macchina.Stato                      (INTEGER)
::AsGlobalPV:Macchina.Manuale                    (BOOL)
::AsGlobalPV:Macchina.Automatico                 (BOOL)
::AsGlobalPV:OreLavoroUtenza.N[x]                (INTEGER)
"""
