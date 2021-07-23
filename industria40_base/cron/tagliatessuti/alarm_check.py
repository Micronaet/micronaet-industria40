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
import pdb
import time
import telepot
import ConfigParser
import pickle
from datetime import datetime

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
pickle_file = os.path.expanduser('./error.status.pickle')
cfg_file = os.path.expanduser('./robot.cfg')
config = ConfigParser.ConfigParser()
config.read([cfg_file])
time_db = {
    'file': 2 * 60,  # file check waiting period (120)
    'telegram': 50,  # Timeout for telegram limit messages (15)
    'error': 15,  # Timeout on error check (30)
}

# -----------------------------------------------------------------------------
# Utility:
# -----------------------------------------------------------------------------
def clean(value):
    value = value or ''
    res = ''
    for c in value:
        if ord(c) > 127:
            res += '#'
        else:
            res += c
    return res


# -----------------------------------------------------------------------------
# Load error comment:
# -----------------------------------------------------------------------------
# Main list:
try:
    file_lines = pickle.load(open(pickle_file, 'rb'))
except:
    file_lines = {}

# -----------------------------------------------------------------------------
# Parameters:
# -----------------------------------------------------------------------------
# File:
path_robot = config.get('File', 'robot')
file_check = config.get('File', 'check')

# Telegram:
telegram_token = config.get('Telegram', 'token')
telegram_group = config.get('Telegram', 'group')
telegram_limit = 10

# Detail:
robot_name = config.get('Detail', 'name')

# -----------------------------------------------------------------------------
# Connect to Telegram:
# -----------------------------------------------------------------------------
bot = telepot.Bot(telegram_token)
bot.getMe()
bot.sendMessage(
    telegram_group,
    '[INFO]: %s: Attivazione procedure controllo allarmi' % robot_name,
)

print('Start alarm procedure master loop')
while True:  # Master loop:
    # -------------------------------------------------------------------------
    # Check file test:
    # -------------------------------------------------------------------------
    while not os.path.isfile(file_check):
        if not os.path.isfile(file_check):
            time.sleep(time_db['file'])

    try:
        bot.sendMessage(
            telegram_group,
            '%s\n[INFO]: Connesso con il Robot: %s' % (
                '-' * 40,
                robot_name,
            )
        )
    except:
        print('Error telegram message: Robot %s connect' % robot_name)

    # -------------------------------------------------------------------------
    # Check alarm loop:
    # -------------------------------------------------------------------------
    while True:
        try:
            filename = datetime.now().strftime('%Y%m%d_err.log')
            if filename not in file_lines:
                file_lines[filename] = 0
            fullname = os.path.join(path_robot, filename)
            if not os.path.isfile(fullname):
                print('Nessun file di errore: %s' % fullname)
                time.sleep(time_db['error'])  # Master period for check error
                continue
            last_total = file_lines[filename]
            row = 0
            print('Check alarm')
            last_error = False
            for line in open(fullname, 'r'):
                row += 1
                if row <= last_total:
                    continue
                if '[AlarmMsg]' not in line:
                    continue
                line_part = line.split(':')[-1].line.split(';')
                if len(line_part) != 4:
                    print('Riga non conforme: %s' % line)
                    file_lines[filename] = row  # Update row total
                    continue

                if line_part == last_error:  # Yet raised
                    continue
                else:  # Not raised
                    # todo raise error out?
                    last_error = line_part

                event_text = \
                    'Robot: %s\n[%s] Messaggio: %s \nDettaglio: %s - %s' % (
                        robot_name,
                        line_part[0] or '',
                        line_part[1] or '',
                        line_part[2] or '',
                        line_part[3] or '',
                        )

                event_text = clean(event_text)
                while True:
                    try:
                        bot.sendMessage(telegram_group, event_text)
                        break
                    except:
                        print(
                            'Telegram error, wait period\n%s' % event_text)
                        time.sleep(time_db['telegram'])  # wait 15 seconds

                file_lines[filename] = row  # Update row total

            print('Write pickle file: %s' % pickle_file)
            pickle.dump(file_lines, open(pickle_file, 'wb'))
            time.sleep(time_db['error'])  # Master period for check error
        except:
            print('Error in file access')
            break
    try:
        bot.sendMessage(
            telegram_group,
            '[WARNING]: Disconnesso dal Robot '
            '(spento o bloccato il programma di controllo?): %s\n%s' % (
                '-' * 40,
                robot_name,
            ))
    except Exception:
        print(Exception)
        print('Telegram error: Robot shutdown?')
pickle.dump(file_lines, load(open(pickle_file, 'wb')))
