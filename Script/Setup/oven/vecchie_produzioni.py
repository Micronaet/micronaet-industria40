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
import pdb
import sys
import erppeek
import ConfigParser
from datetime import datetime, timedelta


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
time_format = '%Y-%m-%d'
mrp_pool = odoo.model('mrp.production')
job_pool = odoo.model('industria.job')

# Select production:
mrp_ids = mrp_pool.search([
    ('state', '=', 'done'),
    ('industria_oven_state', '!=', 'done'),
    ('date_planned', '>=', '2020-01-16'),
    ])
pdb.set_trace()
for mrp in mrp_pool.browse(mrp_ids):
    mrp_date = mrp.date_planned[:10]
    mrp_date_dt = datetime.strptime(mrp_date, time_format)
    job_date_dt = mrp_date_dt - timedelta(days=15)
    dow = job_date_dt.isoweekday()
    if dow == 6:  # Saturday
        job_date_dt -= timedelta(days=1)
    elif dow in (0, 7):  # Sunday
        job_date_dt -= timedelta(days=2)
    job_date = job_date_dt.strftime(time_format)

    this_ids = [mrp.id]
    mrp_pool.industria_oven_state_pending(this_ids)
    mrp_pool.explode_oven_job_per_color(this_ids)

    # Generate new job:
    job = job_pool.generate_oven_all([])
    job_id = job['res_id']
    job_pool.write([job_id], {
        'created_at': '%s 08:15:00' % job_date,
        'endend_at': '%s 11:59:00' % job_date,
    })
