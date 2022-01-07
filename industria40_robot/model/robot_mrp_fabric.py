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


class IndustriaMrp(orm.Model):
    """ Model name: Industria 4.0 MRP
    """

    _name = 'industria.mrp'
    _description = 'Industria 4.0 MRP'
    _order = 'date desc'
    _rec_name = 'date'

    def generate_industria_mrp_line(self, cr, uid, ids, context=None):
        """ Generate lined from MRP production linked
        """
        mrp_id = ids[0]
        i40_mrp = self.browse(cr, uid, mrp_id, context=context)

        line_pool = self.pool.get('industria.mrp.line')
        material_category = 'Tessuti'  # todo manage better

        # Clean previous line:
        _logger.warning('Clean previous line')
        self.write(cr, uid, ids, {
            'line_ids': [(6, 0, [])],
        }, context=context)

        # Collect new line:
        new_lines = {}
        _logger.warning('Generate new lines:')
        for mrp in i40_mrp.mrp_ids:
            for line in mrp.order_line_ids:
                # todo consider also maked?
                todo = (
                    line.product_uom_qty -
                    # line.deliverey_qty
                    # line.product_uom_maked_sync_qty -
                    line.mx_assigned_qty)
                product = line.product_id

                for bom_line in product.dynamic_bom_line_ids:
                    # Check if (category) need fabric operation
                    cmpt_category = bom_line.category_id
                    if cmpt_category.need_fabric:
                        semiproduct = bom_line.product_id
                        component_id = semiproduct.id
                        for cmpt_line in semiproduct.half_bom_ids:
                            material = cmpt_line.product_id
                            category_name = material.inventory_category_id.name
                            if category_name == material_category:
                                key = (component_id, material.id)
                                if key not in new_lines:
                                    new_lines[key] = [0, '']  # total, detail
                                # Updata data:
                                new_lines[key][0] += \
                                    todo * bom_line.product_qty
                                new_lines[key][1] += \
                                    'MRP: %s, Prod: %s >> Semilav [%s] %s >>' \
                                    ' Mat. %s\n' % (
                                        mrp.name,
                                        product.default_code,
                                        cmpt_category.name,
                                        semiproduct.default_code,
                                        material.default_code,
                                    )

        # Generate line:
        _logger.warning('Generate new lines:')
        for key in new_lines:
            todo, detail = new_lines[key]
            product_id, material_id = key
            line_pool.create(cr, uid, {
                'industria_mrp_id': mrp_id,
                'product_id': product_id,
                'material_id': material_id,
                'todo': todo,
                'detail': detail,
            }, context=context)
        return True

    _columns = {
        'date': fields.date(
            'Data', help='Data di creazione'),
        # todo: how assign yet present semi-product?
        # 'picking': fields.many2one(
        # 'stock.picking', 'Documento di impegno', '')
        'state': fields.selection([
            ('draft', 'Draft'),
            ('open', 'Aperto'),
            ('closed', 'Chiuso'),
            ('paused', 'In pausa'),
        ], 'Stato')
    }

    _defaults = {
        'state': lambda *x: 'draft',
    }


class IndustriaMrpLine(orm.Model):
    """ Model name: Industria 4.0 MRP Line
    """

    _name = 'industria.mrp.line'
    _description = 'Industria 4.0 MRP Line'
    _order = 'program_id, product_id, material_id'
    _rec_name = 'material_id'

    def get_detail(self, cr, uid, ids, context=None):
        """ View for detail
        """
        line_id = ids[0]
        model_pool = self.pool.get('ir.model.data')
        # view_id = model_pool.get_object_reference(
        # 'module_name', 'view_name')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Dettaglio riga'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': line_id,
            'res_model': 'industria.mrp.line',
            # 'view_id': view_id,  # False
            'views': [(False, 'form')],  # (False, 'tree'),
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }

    _columns = {
        'industria_mrp_id': fields.many2one(
            'industria.mrp', 'MRP I4.0'),
        'material_id': fields.many2one(
            'product.product', 'Materiale'),
        'product_id': fields.many2one(
            'product.product', 'Semilavorato'),
        'program_id': fields.many2one(
            'industria.program', 'Programma'),

        'detail': fields.text('Dettaglio'),
        'todo': fields.integer('Da fare'),
        'assigned': fields.integer('Assegnati'),
        'produced': fields.integer('Prodotti'),
        'remain': fields.integer(
            'Residui',
            help='Residui da produrre (calcolato da quelli da fare puliti da '
                 'quelli fatti o assegnati'),
    }

    _defaults = {
        'state': lambda *x: 'draft',
    }


class IndustriaJob(orm.Model):
    """ Model name: Job relation
    """
    _inherit = 'industria.job'

    _columns = {
        'industria_mrp_id': fields.many2one(
            'industria.mrp', 'Produzione I40',
            help='Collegamento del job di lavorazione al suo documento di '
                 'produzione principale',
        ),
    }


class MrpProductionOven(orm.Model):
    """ Model name: MrpProductionOven
    """

    _inherit = 'mrp.production'

    _columns = {
        'industria_mrp_id': fields.many2one(
            'industria.mrp', 'Produzione I40',
            help='Collegamento alla bolla di produzione, es. nei tessuti'
                 'è il macro lavoro che genera poi tutti i job unitari'
                 'è possibile collegare più produzioni alla stessa bolla'
        ),
    }


class IndustriaMrpInherit(orm.Model):
    """ Model name: MrpProductionOven
    """

    _inherit = 'industria.mrp'

    _columns = {
        'mrp_ids': fields.one2many(
            'mrp.production', 'industria_mrp_id', 'Produzioni',
            help='Produzioni collegate alla bolla I40 MRP'
        ),
        'job_ids': fields.one2many(
            'industria.job', 'industria_mrp_id', 'Job',
            help='Job generati da questa bolla I4.0 di produzione',
        ),
        'line_ids': fields.one2many(
            'industria.mrp.line', 'industria_mrp_id', 'MRP I4.0',
            help='Sviluppo produzioni per semilavorati da passare alla '
                 'macchina',
        ),
    }
