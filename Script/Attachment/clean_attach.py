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

import erppeek
import ConfigParser
from datetime import datetime

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
company_list = ('fia', 'gpb')

database = {
    'fia': {
        'attachment': {
            0: [
                'Extra_sconti.xlsx',
                'commercializzati.xlsx',
                'Statistiche_Produzioni_',
                'controllo.xlsx',
                'Semilavorati_disponibili_',
                'Order_OC\/',  # residuo minimo
            ],
            1: [
                'Componenti_20',
                'Stato_tessuti_',
                'Tubi.odt',
            ],
        },
        'mail': {
            0: [
                'Invio automatico stato disponibilità materiali',
                'Invio automatico stato extra sconto',
                'Invio automatico statistiche di produzione:',
                'NESSUNA VARIAZIONE EXTRA SCONTO',
                'Ordini senza la scadenza',
                'Fiam S.r.l new product',
                'Check invoice mail database Fiam',
                'Distinte non controllate negli ordini',
                'Fiam S.r.l: Ordine con prodotti nuovi',
                ' ha residuo minimo',  # finale dell'oggetto
            ],
            1: [
                'Invio automatico stato componenti',
                'Invio automatico stato tessuto',
                'Invio automatico stato telai',
            ],
        },
    },

    'gpb': {
        'attachment': {
            0: [
                'Order_OC\/',  # residuo minimo
            ],
        },
        'mail': {
            0: [
                ' ha residuo minimo',  # finale dell'oggetto
                'Check invoice mail database',
                ': Ordine con prodotti nuovi',
                'G.P.B. S.r.l.: Order with new product',
                'G.P.B. S.r.l. new product: ',
                'GPB: Partner senza mail per invio fattura',
                'Ordini in Prestashop dalla data',
                'Prestashop order from',
            ],
        },
    },
}

for company in company_list:
    cfg_filename = '../openerp.%s.cfg' % company
    cfg_file = os.path.expanduser(cfg_filename)

    config = ConfigParser.ConfigParser()
    config.read([cfg_file])
    dbname = config.get('dbaccess', 'dbname')
    user = config.get('dbaccess', 'user')
    pwd = config.get('dbaccess', 'pwd')
    server = config.get('dbaccess', 'server')
    port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

    # -------------------------------------------------------------------------
    # Connect to ODOO:
    # -------------------------------------------------------------------------
    print('Connect to ODOO [%s] Company: %s' % (cfg_file, company))
    odoo = erppeek.Client(
        'http://%s:%s' % (
            server, port),
        db=dbname,
        user=user,
        password=pwd,
        )
    attachment_pool = odoo.model('ir.attachment')
    mail_pool = odoo.model('mail.message')

    year = datetime.now().year
    rest_date = str(datetime.now())[4:19]
    for date in database[company]['attachment']:
        to_date = '%s%s' % (
            year - date,
            rest_date,
        )
        for name in database[company]['attachment'][date]:
            attachment_ids = attachment_pool.search([
                ('create_date', '<=', to_date),
                ('name', '=ilike', '%s%%' % name),
                ])
            total = len(attachment_ids)
            counter = 0

            print('%s. Removing: %s...' % (company, total))
            for attachment_id in attachment_ids:
                counter += 1
                attachment_pool.unlink([attachment_id])
                print('%s. %s di %s. Deleted [%s]' % (
                    company, counter, total, name))

    for date in database[company]['mail']:
        to_date = '%s%s' % (
            year - date,
            rest_date,
        )
        for name in database[company]['mail'][date]:
            mail_ids = mail_pool.search([
                ('create_date', '<=', to_date),
                ('subject', 'ilike', '%s' % name),
                ])
            total = len(mail_ids)
            counter = 0

            print('%s. Removing: %s...' % (company, total))
            for mail_id in mail_ids:
                counter += 1
                mail_pool.unlink([mail_id])
                print('%s. %s di %s. Mail Deleted [%s]' % (
                    company, counter, total, name))
