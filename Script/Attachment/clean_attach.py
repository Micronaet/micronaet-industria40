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
from datetime import datetime

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
cfg_file = os.path.expanduser('../openerp.cfg')  # openerp_gpb.cfg

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
print('Connect to ODOO [%s]' % cfg_file)
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port),
    db=dbname,
    user=user,
    password=pwd,
    )
attachment_pool = odoo.model('ir.attachment')
mail_pool = odoo.model('mail.message')

names = [
    'Extra_sconti.xlsx',
    'commercializzati.xlsx',
    'Statistiche_Produzioni_',
    'controllo.xlsx',
    'Semilavorati_disponibili_',
]

for name in names:
    attachment_ids = attachment_pool.search([
        ('name', '=ilike', '%s%%' % name),
        ])
    total = len(attachment_ids)
    counter = 0
    for attachment_id in attachment_ids:
        counter += 1
        attachment_pool.unlink([attachment_id])
        print('%s di %s. Deleted [%s]' % (counter, total, name))

names = [
    'Invio automatico stato disponibilità materiali',
    'Invio automatico stato extra sconto',
    'Invio automatico statistiche di produzione:',
    'NESSUNA VARIAZIONE EXTRA SCONTO',
    'Ordini senza la scadenza',
    'Fiam S.r.l new product',
    'Check invoice mail database Fiam',
    'Distinte non controllate negli ordini',
    'Fiam S.r.l: Ordine con prodotti nuovi',
]

for name in names:
    mail_ids = mail_pool.search([
        ('subject', '=ilike', '%s%%' % name),
        ])
    total = len(mail_ids)
    counter = 0
    for mail_id in mail_ids:
        counter += 1
        mail_pool.unlink([mail_id])
        print('%s di %s. Mail Deleted [%s]' % (counter, total, name))

