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
import erppeek
import ConfigParser
import pdb


def host_up(host):
    if os.system('ping -c 2 %s' % host) is 0:
        return True
    else:
        return False


# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
cfg_file = os.path.expanduser('../openerp.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port),
    db=dbname,
    user=user,
    password=pwd,
    )

# Pool used:
robot_pool = odoo.model('industria.robot')
database_pool = odoo.model('industria.database')

# -----------------------------------------------------------------------------
# Tagliatubi:
# -----------------------------------------------------------------------------
robot_ids = robot_pool.search([
    ('code', '=', 'TAGL01'),
])
if robot_ids:
    for robot in robot_pool.browse(robot_ids):
        robot.load_all_stat_file()
        print('Update robot: %s' % robot.name)
else:
    print('No TAGL01 robot found')

# -----------------------------------------------------------------------------
#                           Piegatubi, Saldatrice
# -----------------------------------------------------------------------------
# For all database present:
database_ids = database_pool.search([])
for database in database_pool.browse(database_ids):
    ip = database.ip
    if not host_up(ip):
        print('\n[ERR] Host %s is down <<<<' % ip)
        continue

    print('\n[INFO] Host %s is up, updating database %s ...' % (
        ip, database.name))
    if database.mode != 'ftp':
        print('[INFO] Import program')
        database_pool.import_program([database.id])

        print('[INFO] Import robot')
        database_pool.import_robot([database.id])
        # External from IF

        print('[INFO] Import job')
        database_pool.import_job([database.id])
