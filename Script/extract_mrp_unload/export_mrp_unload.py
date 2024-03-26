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
import erppeek
try:
    import ConfigParser
except:
    import configparser as ConfigParser


# -----------------------------------------------------------------------------
#                              Parameters:
# -----------------------------------------------------------------------------
# A: Static
from_date = '2020-09-01'
filename = '/home/administrator/photo/log/mrp_unload__from_%s.xlsx' % from_date

context = {
    'run_force': {
        'from_date': from_date,
        'to_date': False,
        'filename': filename,
        'update': False,  # Only dry run!
        }}

# B: File:
config_file = '../openerp.cfg'
cfg_file = os.path.expanduser(config_file)

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
odoo.context = context

mrp_pool = odoo.model('mrp.production')
mrp_pool.schedule_unload_mrp_material_erpeek()

