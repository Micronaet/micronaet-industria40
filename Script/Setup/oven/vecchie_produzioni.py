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
import time
import erppeek
import ConfigParser
from datetime import datetime, timedelta


# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
# cfg_file = os.path.expanduser('../local.cfg')
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
selection_pool = odoo.model('mrp.production.oven.selected')

# Select production:
mrp_ids = mrp_pool.search([
    ('state', '=', 'done'),
    ('industria_oven_state', '!=', 'done'),
    ('date_planned', '>=', '2020-01-16'),
    ])
pdb.set_trace()
for mrp in mrp_pool.browse(mrp_ids):
    print('Generazione produzione %s' % mrp.name)
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
    print('...Selezione produzione %s' % mrp.name)
    mrp_pool.explode_oven_job_per_color_forced(this_ids)
    print('...Generazione lavori dettagliati %s' % mrp.name)

    # Generate new job:
    job = selection_pool.generate_oven_job_all([])
    print('...Generazione job')
    job_id = job.get('res_id')
    if job_id:
        job_ids = [job_id]
    else:
        job_ids = job['domain'][0][2]
    print('...Riassegnazione data')
    if job_ids:
        job_pool.write(job_ids, {
            'created_at': '%s 08:00:00' % job_date,
            'endend_at': '%s 12:00:00' % job_date,
        })
    print('Completata %s' % mrp.name)
