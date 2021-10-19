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

    def industria_oven_state_pending(self, cr, uid, ids, context=None):
        """ Update state pending
        """
        return self.write(cr, uid, ids, {
            'industria_oven_state': 'pending',
        }, context=context)

    def industria_oven_state_none(self, cr, uid, ids, context=None):
        """ Update state pending
        """
        return self.write(cr, uid, ids, {
            'industria_oven_state': 'none',
        }, context=context)

    def industria_oven_state_done(self, cr, uid, ids, context=None):
        """ Update state done
        """
        return self.write(cr, uid, ids, {
            'industria_oven_state': 'done',
        }, context=context)

    def explode_oven_job_per_color(self, cr, uid, ids, context=None):
        """ Generate Oven job
        """
        pre_oven_pool = self.pool.get('mrp.production.oven.selected')
        model_pool = self.pool.get('ir.model.data')

        # Search selected items
        mrp_ids = self.search(cr, uid, [
            ('industria_oven_state', '=', 'pending'),
        ], context=context)

        # Collect data:
        for mrp in self.browse(cr, uid, mrp_ids, context=context):
            date_planned = mrp.date_planned[:10]
            mrp_name = mrp.name
            lines = mrp.order_line_ids
            total = len(lines)
            counter = 0
            for line in lines:
                counter += 1
                if not counter % 10:
                    _logger.info(
                        'MRP %s: %s on %s' % (mrp_name, counter, total))
                default_code = line.product_id.default_code
                parent_code = default_code[:3].strip()
                color_code = default_code[6:8].strip()
                if not color_code or line.mx_closed:
                    continue  # neutral color or closed line (jump)

                # Get remain:
                remain_mrp = (
                        line.product_uom_qty - line.mx_assigned_qty -
                        line.product_uom_maked_sync_qty)
                remain_delivery = line.product_uom_qty - line.delivered_qty
                # todo consider also job yet forked!!
                if remain_delivery > remain_mrp:  # Use minor
                    remain = remain_mrp
                else:
                    remain = remain_delivery
                if remain:
                    pre_oven_pool.create(cr, uid, {
                        'send': False,
                        'parent_code': parent_code,
                        'color_code': color_code,
                        'total': remain,
                        'partial': 0,
                        'from_date': date_planned,
                        'to_date': date_planned,
                        'mrp_id': mrp.id,
                    }, context=context)

        tree_id = model_pool.get_object_reference(
            cr, uid,
            'industria40_robot', 'view_mrp_production_oven_selected_tree')[1]
        graph_id = model_pool.get_object_reference(
            cr, uid,
            'industria40_robot', 'view_mrp_production_oven_selected_graph')[1]
        self.industria_oven_state_done(cr, uid, mrp_ids, context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pre forno'),
            'view_type': 'form',
            'view_mode': 'tree,graph',
            # 'res_id': false,
            'res_model': 'mrp.production.oven.selected',
            'view_id': tree_id,
            'views': [(tree_id, 'tree'), (graph_id, 'graph')],
            'domain': [],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }

    _columns = {
        'industria_oven_state': fields.selection([
            ('none', 'Non impostato'),
            ('pending', 'Pendente da fare'),
            ('done', 'Fatto'),
            ],
            'Stato forno',
            help='Indica se il lavoro è stato girato al forno o fatto'),
    }

    _defaults = {
        'industria_oven_state': lambda *x: 'none',
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
        'mrp_id': fields.many2one('mrp.production', 'Produzione'),
    }


class MrpProductionOven(orm.Model):
    """ Model name: MrpProductionOven
    """

    _inherit = 'mrp.production'

    _columns = {
        'oven_pre_job_ids': fields.one2many(
            'mrp.production.oven.selected', 'mrp_id',
            'Pre-Job forno'),
    }
