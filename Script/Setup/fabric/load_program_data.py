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
file_csv = './I40 program tessuti.csv'
cols = 15
product_id = 32508  # AUTOMRP product

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
program_pool = odoo.model('industria.program')
fabric_pool = odoo.model('industria.program.fabric')
part_pool = odoo.model('industria.program.fabric.part')

counter = 0

# -----------------------------------------------------------------------------
# Clean all operation:
# -----------------------------------------------------------------------------
fabric_ids = fabric_pool.search([])
fabric_pool.unlink(fabric_ids)

part_ids = part_pool.search([])
part_pool.unlink(part_ids)


def clean_float(value):
    return float((value or '0').replace(',', '.'))


log_f = open('import.log', 'w')


def write_log(log_f, message, verbose=True):
    """ Write log
    """
    log_f.write(message)
    log_f.write('\n')
    log_f.flush()
    if verbose:
        print(message)


for line in open(file_csv, 'r'):
    counter += 1
    if counter == 1:
        continue

    row = line.split('|')

    if len(row) != cols:
        write_log(log_f, '%s. Different column!' % counter)
        continue

    program_id = int(row[0])
    name = row[2]
    jump = row[1].upper() == 'X'
    if jump:
        write_log(log_f, '%s. Jump %s' % (counter, name))
        continue
    mask = (row[7] or '')
    try:
        total = clean_float(row[8])
    except:
        write_log(log_f, '%s. Error reading total, jumped: %s' % (
            counter, name))
        continue

    length = clean_float(row[13]) * 1000.0

    if mask:
        mask += '%'

    # Select production:
    program_ids = program_pool.search([
        ('id', '=', program_id),
        ('name', '=', name),
    ])

    if program_ids:
        message = '%s. Updating program: %s' % (counter, name)
    else:
        program_ids = program_pool.search([
            ('id', '=', program_id),
            ])
        message = '%s. Non trovato programma %s cercato per ID %s' % (
            counter, name, program_id)

    if not program_ids:
        write_log(log_f,
                  '%s. Programma non trovato ne per ID %s ne per nome %s' % (
                      counter, program_id, name))
        continue

    # -------------------------------------------------------------------------
    # Update program:
    # -------------------------------------------------------------------------
    # Update total length:
    program_pool.write(program_ids, {
        'fabric_length': length,
        })

    # -------------------------------------------------------------------------
    # Create fabric record:
    # -------------------------------------------------------------------------
    fabric_id = fabric_pool.create({
        'program_id': program_ids[0],
        'fabric_id': product_id,
        }).id

    # -------------------------------------------------------------------------
    # Create fabric part record:
    # -------------------------------------------------------------------------
    part_id = part_pool.create({
        'fabric_id': fabric_id,
        'total': total,
        'mask': mask,
        })

    # Associate program:
    program_pool.button_generate_matching_product_program([program_id])
    write_log(log_f, message)
