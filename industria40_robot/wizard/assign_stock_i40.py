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


class IndustriaAssignStockWizard(orm.TransientModel):
    """ Wizard assign stock
    """
    _name = 'industria.assign.stock.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_assign(self, cr, uid, ids, context=None):
        """ Event for button done
        """
        if context is None:
            context = {}

        wizard = self.browse(cr, uid, ids, context=context)[0]

        return {
            'type': 'ir.actions.act_window_close'
            }

    def _get_wizard_information(
            self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}

        wizard_id = ids[0]
        wizard = self.browse(cr, uid, wizard_id, context=context)
        product = wizard.industria_line_id.product_id

        res[wizard_id] = {
            'available_qty': product.mx_net_mrp_qty,
            'current_qty': wizard.stock_move_id.product_uom_qty,  # todo check
        }
        return res

    _columns = {
        'industria_line_id': fields.many2one(
            'industria.mrp.line', 'Linea', readonly=True,
            help='Semilavorato selezionato nella riga'),
        'available_qty': fields.function(
            _get_wizard_information, method=True, readonly=True,
            type='float', string='Disponibile a magazzino', multi=True,
            ),
        'current_qty': fields.function(
            _get_wizard_information, method=True, readonly=True,
            type='float', string='Attuali assegnati', multi=True,
            ),
        'total_qty': fields.function(
            _get_wizard_information, method=True, readonly=True,
            type='float', string='Fabbisogno', multi=True,
            ),
        'new_qty': fields.float(
            'Nuova', digits=(16, 2), required=True),
        }
