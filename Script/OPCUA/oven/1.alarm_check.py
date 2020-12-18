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

# Load Telegram BOT:
bot = telepot.Bot(telegram_token)
bot.getMe()

# Master loop:
robot = False

bot.sendMessage(
    telegram_group,
    u'%s\n[INFO] PC: %s Avvio script di controllo...' % ('-' * 80, check_from),
)
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
                u'[INFO] Connessione con robot (inizio monitoraggio)',
            )
        except:
            # Wait and repeat
            time.sleep(wait['robot'])
            continue

    # -------------------------------------------------------------------------
    # Phase 2: Check alarms:
    # -------------------------------------------------------------------------
    try:
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
del robot
