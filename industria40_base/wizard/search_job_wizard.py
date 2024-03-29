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
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)


_logger = logging.getLogger(__name__)


class IndustriaJobBarcodeSearchWizard(orm.TransientModel):
    """ Wizard for search barcode job
    """
    _name = 'industria.job.barcode.search.wizard'

    def open_job(self, cr, uid, barcode, context=None):
        """ Utility function
        """
        if context is None:
            context = {}

        if not barcode:
            _logger.error('No barcode!')
            return False
        job_id = int(barcode.strip().split()[0])

        model_pool = self.pool.get('ir.model.data')
        form_view_id = model_pool.get_object_reference(
            cr, uid,
            'industria40_base',
            'view_industria_job_opcua_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Cerca Job'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': job_id,
            'res_model': 'industria.job',
            'view_id': form_view_id,
            'views': [(form_view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    # --------------------
    # Wizard button event:
    # --------------------
    def onchange_barcode(self, cr, uid, ids, barcode, context=None):
        """ Call search
        """
        if barcode:
            _logger.info('Found Barcode: %s' % barcode)
            return self.open_job(cr, uid, barcode, context=context)
        else:
            return False

    def action_search(self, cr, uid, ids, context=None):
        """ Event for button done
        """
        if context is None:
            context = {}

        wizard_browse = self.browse(cr, uid, ids, context=context)[0]
        barcode = wizard_browse.barcode or ''
        if barcode:
            return self.open_job(cr, uid, barcode, context=context)
        else:
            return False

    _columns = {
        'barcode': fields.char(
            'Codice a barre',
            help='Scansionare il codice a barre per cercare il job '
                 'generatore'),
        }
