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
import pdb
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

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------
    def action_assign(self, cr, uid, ids, context=None):
        """ Event for button done
        """
        i40_pool = self.pool.get('industria.mrp')
        i40_line_pool = self.pool.get('industria.mrp.line')

        wizard = self.browse(cr, uid, ids, context=context)[0]
        line = wizard.product_id
        industria_line_id = wizard.industria_line_id.id
        assigned = wizard.new_qty

        # Not created stock.move and picking just save number:
        i40_line_pool.write(cr, uid, [industria_line_id], {
            'assigned': assigned
        }, context=context)
        # i40_line_pool.industria_get_movement(
        #    cr, uid, [industria_line_id], assigned, context=context)

        # Write chatter message:
        i40_pool.write_log_chatter_message(
            cr, uid, [industria_line_id],
            'Assegnato q. magazzino %s a semilavorato: %s' % (
                assigned,
                line.material_id.default_code,
            ),
            context=context)

        return {'type': 'ir.actions.act_window_close'}

    _columns = {
        'industria_line_id': fields.many2one(
            'industria.mrp.line', 'Linea', readonly=True,
            help='Semilavorato selezionato nella riga'),
        'available_qty': fields.float(
            'Disponibile a magazzino', digits=(16, 2), readonly=True,
            ),
        'locked_qty': fields.float(
            'Attuali assegnati', digits=(16, 2), readonly=True,
            ),
        'produced_qty': fields.float(
            'Già lavorati', digits=(16, 2), readonly=True,
            ),
        'total_qty': fields.float(
            'Fabbisogno totale', digits=(16, 2), readonly=True,
            ),
        'remain_qty': fields.float(
            'Magazzino usabile (max)', digits=(16, 2), readonly=True,
            ),
        'new_qty': fields.float(
            'Nuova', digits=(16, 2)),
        'comment': fields.text('Commento', readonly=True),
        }
