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

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
cfg_file = os.path.expanduser('./robot.cfg')
config = ConfigParser.ConfigParser()
config.read([cfg_file])

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
error_comment = pickle.load(open('./error_comment.pickle', 'r'))

# Exclude list:
file_err = open('./exclude.csv', 'r')
warning_error = []
for line in file_err:
    line = line.strip()
    try:
        warning_error.append(int(line))
    except:
        print('Exclude code not found: %s' % line)

# -----------------------------------------------------------------------------
# FTP Access:
# -----------------------------------------------------------------------------
ftp_user = config.get('FTP', 'user')
ftp_password = config.get('FTP', 'password')
ftp_host = config.get('FTP', 'host')
ftp_mountpoint = config.get('FTP', 'mountpoint')
ftp_folder = os.path.join(
    ftp_mountpoint,  config.get('FTP', 'folder'))
ftp_check = os.path.join(
    ftp_mountpoint,  config.get('FTP', 'check'))

mount_command = 'curlftpfs %s:%s@%s %s' % (
    ftp_user,
    ftp_password,
    ftp_host,
    ftp_mountpoint,
)
umount_command = 'umount -l %s' % ftp_mountpoint

# -----------------------------------------------------------------------------
# Telegram parameters:
# -----------------------------------------------------------------------------
telegram_token = config.get('Telegram', 'token')
telegram_group = config.get('Telegram', 'group')
telegram_limit = 10

# -----------------------------------------------------------------------------
# Robot parameters:
# -----------------------------------------------------------------------------
robot_name = config.get('robot', 'name')
start = config.get('robot', 'start')

# Token for extract data from file:
error_code = config.get('robot', 'token_error')
date = config.get('robot', 'token_date')

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
    # A. Mount server:
    print('Try to mount robot server')
    while not os.path.isfile(ftp_check):
        try:
            os.system(umount_command)
        except:
            print('Warning umount %s folder (no problem, not an error)' %
                  ftp_folder)  # Try umount previously
        try:
            os.system(mount_command)
        except:
            print('Pending mounting robot in %s...' % ftp_mountpoint)
        if not os.path.isfile(ftp_check):
            time.sleep(2 * 60)

    try:
        bot.sendMessage(
            telegram_group,
            '%s\n[INFO]: Connesso con il Robot: %s' % (
                '-' * 40,
                robot_name,
            )
        )
    except:
        print('Error telegram message: Robot connect')

    # B. Check alarm loop:
    while True:
        try:
            print('Check alarm')
            clean_file = []
            error_counter = 0
            for root, folders, files in os.walk(ftp_folder):
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
                            code = abs(int(data['error_code'][1]))
                            message = error_comment.get(
                                code,
                                'Codice error non presente nella tabella: %s'
                                % code)
                            # Manage unnecessary messages here
                            if code in warning_error:
                                relevance = 'BASSA'
                            else:
                                relevance = 'ALTA'

                            event_text = \
                                'Importanza: %s\nRobot: %s\nDate: %s\n' \
                                'Messaggio: %s' % (
                                    relevance,
                                    robot_name,
                                    data['date'],
                                    message,
                                    )

                            # Telegram message limit prevent:
                            if error_counter > telegram_limit:
                                error_counter = 0
                                print('Telegram wait period...')
                                time.sleep(15)  # wait 15 seconds
                            else:
                                error_counter += 1
                            event_text = clean(event_text)
                            bot.sendMessage(telegram_group, event_text)
                            clean_file.append(fullname)

                            # Clean file:
                            print('Removing: %s' % fullname)
                            try:
                                print('Clean file used: %s' % fullname)
                                os.remove(fullname)
                            except:
                                print('Problem removing file: %s' % fullname)

                            print(event_text.replace('\n', ' - '))
                break  # No subfolder

            # Clean alarm used:
            # if clean_file:
            #    print('Clean file used')
            #    for fullname in clean_file:
            #        print('Removing: %s' % fullname)
            #        os.remove(fullname)
            time.sleep(30)  # Master period for check error
        except:
            print('Error in FTP access')
            break

    try:
        bot.sendMessage(
            telegram_group,
            '[WARNING]: Disconnesso dal Robot (spento o bloccato il programma '
            'di controllo?): %s\n%s' % (
                '-' * 40,
                robot_name,
            ))
    except:
        print('Telegram error: Robot shutdown?')
