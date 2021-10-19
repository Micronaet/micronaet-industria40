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
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare)


_logger = logging.getLogger(__name__)


class MrpProductionOven(orm.Model):
    """ Model name: MrpProductionOven
    """

    _inherit = 'mrp.production'

    def explode_oven_job_per_color(self, cr, uid, ids, context=None):
        """ Generate Oven job
        """
        pre_oven_pool = self.pool.get('mrp.production.oven.selected')
        model_pool = self.pool.get('ir.model.data')

        # Search selected items
        mrp_ids = self.search(cr, uid, [
            ('industria_oven_pending', '=', True),
        ], context=context)

        # Collect data:
        explode = {}
        for mrp in self.browse(cr, uid, mrp_ids, context=context):
            for line in mrp.order_line_ids:
                default_code = line.product_id.default_code
                parent_code = default_code[:3].strip()
                color_code = default_code[6:8].strip()
                if not color_code:
                    continue  # neutral color
                key = (parent_code, color_code)
                if key not in explode:
                    explode[key] = [0, []]

                # Get remain:
                remain_mrp = (
                        line.product_uom_qty - line.mx_assigned_qty -
                        line.product_uom_maked_sync_qty)
                remain_delivery = line.product_uom_qty - line.delivered_qty
                if remain_delivery > remain_mrp:  # Use minor
                    remain = remain_mrp
                else:
                    remain = remain_delivery
                if remain:
                    explode[key][0] += remain
                    explode[key][1].append(mrp)

        # ---------------------------------------------------------------------
        # Generate wizard procedure:
        # ---------------------------------------------------------------------
        # Clean previous:
        pre_ids = pre_oven_pool.search(cr, uid, [], context=context)
        if pre_ids:
            pre_oven_pool.unlink(cr, uid, pre_ids, context=context)

        # Generate new:
        pdb.set_trace()
        for key in explode:
            parent_code, color_code = key
            total, mrps = explode[key]
            date = [False, False]
            mrp_ids = []
            for mrp in mrps:
                date_planned = mrp.date_planned[:10]
                if not date[0] or date_planned < date[0]:
                    date[0] = date_planned
                if not date[1] or date_planned > date[1]:
                    date[1] = date_planned
                mrp_ids.append(mrp.id)

            pre_oven_pool.create({
                'send': False,
                'parent_code': parent_code,
                'color_code': color_code,
                'total': total,
                'partial': 0,
                'from_date': date[0],
                'to_date': date[1],
                'mrp_ids': [(6, 0, mrp_ids)],
            })
        tree_id = model_pool.get_object_reference(
            cr, uid,
            'industria40_robot', 'view_mrp_production_oven_selected_tree')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pre forno'),
            'view_type': 'form',
            'view_mode': 'tree',
            # 'res_id': false,
            'res_model': 'mrp.production.oven.selected',
            'view_id': tree_id,
            'views': [(tree_id, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    _columns = {
        'industria_oven_pending': fields.boolean(
            'Da verniciare',
            help='Marcare la produzione per essere verniciata'),
    }


class MrpProductionOvenSelected(orm.Model):
    """ Wizard name: class Mrp Production Oven Selected
    """

    _name = 'mrp.production.oven.selected'
    _description = 'Pre selection wizard'
    _order = 'parent_code, color_code'
    _rec_name = 'parent_code'

    def generate_oven_job(self, cr, uid, ids, context=None):
        """ Generate Oven job
        """

        return True

    _columns = {
        'send': fields.boolean('Da spedire'),
        'parent_code': fields.char(
            'Codice padre', size=5, required=True),
        'color_code': fields.char(
            'Codice colore', size=5, required=True),
        'total': fields.integer('Totali'),
        'partial': fields.integer(
            'Parziali', help='Pezzi parziali da mandare in lavorazione'),
        'from_date': fields.date('Dalla data'),
        'to_date': fields.date('Alla data'),
        'mrp_ids': fields.many2many(
            'mrp.production', 'i40_oven_mrp_rel',
            'wizard_id', 'mrp_id',
            'Produzioni'),
    }
