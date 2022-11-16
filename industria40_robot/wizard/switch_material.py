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


class IndustriaAssignMaterialWizard(orm.TransientModel):
    """ Wizard assign new material
    """
    _name = 'industria.assign.material.wizard'

    def onchange_current_material_id(
            self, cr, uid, ids, current_material_id, context=None):
        """ On change setup domain
        """
        product_pool = self.pool.get('product.product')
        res = {}

        if not current_material_id:
            return res

        product = product_pool.browse(
            cr, uid, current_material_id, context=context)
        default_code = product.default_code
        if not default_code:
            return res

        new_mask = ''
        part = 0
        for c in default_code:
            if c.isalpha():
                new_mask += c
                if part == 1:
                    part = 2  # Stop replace number
                continue

            if c.isdigit():
                if not part:
                    part = 1

                if part == 1:  # Replace number:
                    new_mask += '_'

        product_ids = product_pool.search(cr, uid, [
            ('default_code', '=ilike', new_mask),
            ('default_code', '!=', default_code),  # Remove current and less H
            ], context=context)
        if not product_ids:
            res['warning'] = {
                'title': 'Errore',
                'message': 'Tessuto non sostituibile %s' % default_code,
            }

        if len(product_ids) == 1:
            res['value'] = {
                'new_material_id': product_ids[0],
                }

        if new_mask:
            res['domain'] = {
                'new_material_id': [('id', 'in', product_ids)],
            }
        return res

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------
    def action_assign(self, cr, uid, ids, context=None):
        """ Event for button done
        """
        i40_pool = self.pool.get('industria.mrp')
        i40_line_pool = self.pool.get('industria.mrp.line')

        wizard = self.browse(cr, uid, ids, context=context)[0]
        mode = wizard.mode
        this_line = wizard.industria_line_id
        industria_line_id = this_line.id

        current_material = wizard.current_material_id
        current_material_id = current_material.id
        new_material = wizard.new_material_id
        new_material_id = new_material.id

        if not this_line:
            raise osv.except_osv(
                _('Errore aggiornamento'),
                _('Non trovata la riga originale da aggiornare'))

        if not current_material_id or not new_material_id:
            return True

        fabric_code = new_material.default_code
        i40_id = this_line.industria_mrp_id.id
        if mode == 'all':
            line_ids = i40_line_pool.search(cr, uid, [
                ('industria_mrp_id', '=', i40_id),
                ('version', '=', 0),  # not linked to job
                ('material_id', '=', current_material_id),  # old line
                # paused will be included!
            ], context=context)
            _logger.info('Selected # %s lines' % len(line_ids))
        else:
            line_ids = [industria_line_id]
            _logger.info('Selected # current line')

        fabric, layer_fabric, color_part = i40_pool.extract_fabric_part(
            fabric_code)

        i40_line_pool.write(cr, uid, line_ids, {
            'material_id': new_material_id,
            'fabric': fabric,
            'color': color_part,
            }, context=context)

        message = 'Forzato cambio colore modo %s da %s a %s ' \
                  '[Righe coinvolte: %s]' % (
                        mode,
                        current_material.default_code,
                        new_material.default_code,
                        len(line_ids)
                        )
        i40_pool.write_log_chatter_message(
            cr, uid, [i40_id], message, context=context)
        return True

    _columns = {
        'industria_line_id': fields.many2one(
            'industria.mrp.line', 'Linea', readonly=True,
            help='Attuale linea semilavorato con il tessuto da cambiare'),
        'current_material_id': fields.many2one(
            'product.product', 'Attuale', readonly=True,
            help='Attuale tessuto utilizzato dalla lavorazione'),
        'new_material_id': fields.many2one(
            'product.product', 'Nuovo tessuto da usare', required=True,
            ),
        'mode': fields.selection([
            ('all', 'Tutte le righe (non assegnate a job)'),
            ('this', 'Solo la riga corrente'),
            ], 'Modalità', required=True)
        }

    _defaults = {
        'mode': lambda *x: 'all',
        }
