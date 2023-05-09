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

import sys
import os
import erppeek
import shutil
import pymssql
import pdb
import ConfigParser
import excel_export
from datetime import datetime


# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
cfg_file = os.path.expanduser('./odoo.cfg')
all_mode = True

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

# Filesystem:
root_path = config.get('dbaccess', 'root')
root_path = os.path.expanduser(root_path)  # Base folder

odoo = erppeek.Client(
    'http://%s:%s' % (server, port),
    db=dbname,
    user=user,
    password=pwd,
    )

robot_pool = odoo.model('industria.robot')
job_pool = odoo.model('industria.job')

# -----------------------------------------------------------------------------
# Generate XLSX files:
# -----------------------------------------------------------------------------
ExcelWriter = excel_export.excel_wrapper.ExcelWriter

# -----------------------------------------------------------------------------
#                         Excel report:
# -----------------------------------------------------------------------------
# Start from last 2 month:
dt = datetime.now()
year = dt.year
month = dt.month
if month == 1:
    month = 12
    year -= 1

# All mode:
if all_mode:
    from_date = '1900-01-01 00:00:00'
else:
    from_date = '%s-%s-01 00:00:00' % (year, month)

robot_ids = robot_pool.search([])
for robot in robot_pool.browse(robot_ids):
    robot_id = robot.id
    robot_code = robot.code
    job_ids = job_pool.search([
        ('source_id', '=', robot_id),
        ('created_at', '>=', from_date),
        ])
    job_ids = job_ids[::-1]  # Reverse order

    previous_period = False
    if not job_ids:
        print('No job for robot: %s' % robot.name)
        continue
    excel_format = {}  # Replaced
    WB = {}  # Replaced
    for job in job_pool.browse(job_ids):
        created_at = job.created_at
        piece = job.piece
        program = job.program_id
        if program:
            program_name = program.name
        else:
            program_name = 'Sconosciuto'

        # Period = Year, month
        this_period = created_at[:4], created_at[5:7]
        if previous_period != this_period:
            previous_period = this_period
            path = os.path.join(
                root_path, robot_code, this_period[0], this_period[1])
            os.system('mkdir -p %s' % path)

            filename = '%s_%s_%s.xlsx' % (
                robot_code, this_period[0], this_period[1])
            fullname = os.path.join(path, filename)
            if os.path.isfile(fullname):
                print('Remove yet present file: %s' % fullname)
                os.remove(fullname)
            else:
                print('New file: %s' % fullname)

            # -----------------------------------------------------------------
            # New Excel file:
            # -----------------------------------------------------------------
            WB = ExcelWriter(fullname, verbose=True)
            ws_name = u'Job robot %s' % robot.code
            WB.create_worksheet(ws_name)

            # Load formats:
            excel_format = {
                'header': WB.get_format('header'),
                'black': {
                    'text': WB.get_format('text'),
                    'number': WB.get_format('number'),
                },
                'red': {
                    'text': WB.get_format('bg_red'),
                    'number': WB.get_format('bg_red_number'),
                },
                'green': {
                    'text': WB.get_format('bg_green'),
                    'number': WB.get_format('bg_green_number'),
                },
            }

            WB.column_width(ws_name, [
                20, 20,
                20, 20,
                10, 10, 10,
                5,
                10,
            ])

            # Print header
            row = 0
            header = [
                'Robot',
                'Programma',
                'Inizio', 'Fine',
                'T. Cambio', 'T. Totale', 'T. Setup',
                'Fuori stat.',
                'Pz.'
            ]
            WB.write_xls_line(ws_name, row, header, excel_format['header'])
            # excel_pool.autofilter(ws_name, row, 0, row, len(header) - 1)
            # excel_pool.freeze_panes(ws_name, row + 1, 4)

        not_consider = job.duration_not_considered
        data = [
            robot.name,
            program_name,
            job.created_at,
            job.ended_at,
            job.duration_change_total,
            job.duration_change_gap,
            job.duration_setup,
            'X' if not_consider else '',
            piece or 1,  # todo where is used?
        ]
        if not_consider:
            color = excel_format['red']
        else:
            color = excel_format['black']

        row += 1
        WB.write_xls_line(ws_name, row, data, color['text'])
    WB.close_workbook()
