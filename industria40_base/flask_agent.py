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
import logging
import openerp
import requests
import json
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)

_logger = logging.getLogger(__name__)


class ResCompany(orm.Model):
    """ Model name: Industria Program
    """

    _inherit = 'res.company'

    def flask_ping(self, cr, uid, ids, context=None):
        """ Flask ping
        """
        # ---------------------------------------------------------------------
        # Authenticate to get Session ID:
        # ---------------------------------------------------------------------
        company = self.browse(cr, uid, ids, context=context)[0]

        url = 'http://%s:%s%s' % (
            company.flask_host,
            company.flask_port,
            company.flask_endpoint,
        )
        _logger.info('Calling Flask test: %s' % url)

        headers = {
            'content-type': 'application/json',
            }
        payload = {
            'jsonrpc': '2.0',
            'params': {
                'command': 'ping',
                'parameters': {},
                },
        }

        response = requests.post(
            url, headers=headers, data=json.dumps(payload))
        response_json = response.json()
        if response_json['success']:
            raise osv.except_osv(
                _('Flask test:'),
                _('Flask collegato e risponde!'))
        else:
            raise osv.except_osv(
                _('Flask test:'),
                _('Errore, Flask non collegato, controllar l\'agent!'))

    _columns = {
        'flask_host': fields.char('Flask Host', size=80, required=True),
        'flask_port': fields.integer('Flask port', required=True),
        'flask_endpoint': fields.char('Flask endpoint', required=True, size=100),
        }

    _defaults = {
        'flask_host': lambda *x: '192.168.1.1',
        'flask_port': lambda *x: 5000,
        'flask_endpoint': lambda *x: '/API/v1.0/micronaet/launcher',
    }
