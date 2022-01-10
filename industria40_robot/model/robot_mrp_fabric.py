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


class ProductProductIndustriaJob(orm.Model):
    """ Model name: Product
    """
    _inherit = 'product.product'

    _columns = {
        'industria_rule_ids': fields.many2many(
            'industria.program.fabric.part', 'product_industria_part_rel',
            'product_id', 'part_id',
            'Regola assegnazione'),
        }


class IndustriaRobotColor(orm.Model):
    """ Model name: Industria 4.0 MRP
    """

    _name = 'industria.robot.color'
    _description = 'Industria Robot color'
    _order = 'sequence'

    _columns = {
        'code': fields.char('Colore', size=10, required=True),
        'replace': fields.char(
            'Rimpiazza', size=10,
            help='A volte i codici hanno delle parti non standard questo'
                 'valore rimpiazzarebbe il codice all\'interno della'
                 'stessa produzione, vedi: TESTNT/NE'),
        'sequence': fields.integer('Ord.'),
        'name': fields.char('Descrizione', size=60, required=True),
        'robot_id': fields.many2one('industria.robot', 'Robot'),
    }


class IndustriaProgram(orm.Model):
    """ Model name: Industria Program
    """

    _inherit = 'industria.program'

    _columns = {
        'max_layer': fields.integer(
            'Massimo numero strati',
            help='Totale teorico degli strati di questo programma, notare che'
                 'potrebbero dipendere anche dal tipo di tessuto scelto!'
                 'Note: Force the one present in Robot'),
        'max_gap': fields.integer(
            'Massimo gap',
            help='Massimo numero di gap che possono esserci tra un gradino'
                 'e l\'altro'
                 'Note: Force the one present in Robot'),
    }


class IndustriaRobot(orm.Model):
    """ Model name: Industria 4.0 MRP
    """

    _inherit = 'industria.robot'

    _columns = {
        'color_ids': fields.one2many(
            'industria.robot.color', 'robot_id', 'Colori'),
        'max_layer': fields.integer(
            'Massimo numero strati',
            help='Totale teorico degli strati di questo programma, notare che'
                 'potrebbero dipendere anche dal tipo di tessuto scelto!'),
        'max_gap': fields.integer(
            'Massimo gap',
            help='Massimo numero di gap che possono esserci tra un gradino'
                 'e l\'altro'),
        }


class IndustriaMrp(orm.Model):
    """ Model name: Industria 4.0 MRP
    """

    _name = 'industria.mrp'
    _description = 'Industria 4.0 MRP'
    _order = 'date desc'
    _rec_name = 'date'

    def generate_industria_job(self, cr, uid, ids, context=None):
        """ Generate job from exploded component
        """
        job_pool = self.pool.get('industria.job')
        step_pool = self.pool.get('industria.job.step')
        fabric_pool = self.pool.get('industria.job.fabric')

        # Clean all job if draft:
        industria_mrp_id = ids[0]
        industria_mrp = self.browse(cr, uid, industria_mrp_id, context=context)

        if industria_mrp.job_ids and \
                {'DRAFT'} == set([job.state for job in industria_mrp.job_ids]):
            job_ids = [job.id for job in industria_mrp.job_ids]
            job_pool.unlink(cr, uid, job_ids, context=context)
            _logger.warning('Deleted %s jobs' % len(job_ids))

        program_created = {}
        sequence = 0
        for line in industria_mrp.line_ids:
            sequence += 1  # Sequence still progress for all program!
            program = line.program_id
            if not program:  # todo raise error?
                _logger.error('Line without program')
                continue
            robot = program.source_id
            database = robot.database_id
            part = line.part_id
            fabric = line.material_id
            block = part.total
            total = line.todo  # todo use line.remain

            # todo what to do with waste?
            extra_block = total % block > 0
            total_layers = int(total / block) + (1 if extra_block else 0)

            # todo check max number of layer for create new job!
            if program not in program_created:
                job_id = job_pool.create(cr, uid, {
                    'created_at': datetime.now().strftime(
                        DEFAULT_SERVER_DATETIME_FORMAT),
                    'source_id': robot.id,
                    'database_id': database.id,
                    'industria_mrp_id': industria_mrp_id,
                    'program_id': program.id,  # Always one so put in header!
                }, context=context)
                step_id = step_pool.create(cr, uid, {
                    'job_id': job_id,
                    'sequence': 1,
                    'program_id': program.id,
                }, context=context)
                program_created[program] = job_id, step_id

            # Create layer
            job_id, step_id = program_created[program]
            fabric_pool.create(cr, uid, {
                'sequence': sequence,
                'step_id': step_id,
                'fabric_id': fabric.id,
                'total': total_layers,
            }, context=context)
        return True

    def generate_industria_mrp_line(self, cr, uid, ids, context=None):
        """ Generate lined from MRP production linked
        """
        color_pool = self.pool.get('industria.robot.color')

        # Load color
        color_db = {}
        color_ids = color_pool.search(cr, uid, [], context=context)
        for color in color_pool.browse(cr, uid, color_ids, context=context):
            color_db[color.code] = color

        mrp_id = ids[0]
        i40_mrp = self.browse(cr, uid, mrp_id, context=context)
        robot_id = i40_mrp.robot_id.id

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
                        for cmpt_line in semiproduct.half_bom_ids:
                            material = cmpt_line.product_id
                            category_name = material.inventory_category_id.name
                            if category_name == material_category:
                                key = (semiproduct, material)
                                if key not in new_lines:
                                    new_lines[key] = [0, '']  # total, detail
                                # Updata data:
                                bom_qty = bom_line.product_qty
                                total_qty = todo * bom_qty
                                new_lines[key][0] += total_qty
                                new_lines[key][1] += \
                                    '[MRP: %s] %s x [PR. %s] >> ' \
                                    '%s x [SL. (%s) %s] >> ' \
                                    '[MP. %s] = %s\n' % (
                                        mrp.name,
                                        int(todo),
                                        product.default_code,
                                        int(bom_qty),
                                        cmpt_category.name,
                                        semiproduct.default_code,
                                        material.default_code,
                                        int(todo * bom_qty),
                                    )

        # Generate line:
        _logger.warning('Generate new lines:')
        for key in new_lines:
            todo, detail = new_lines[key]
            semiproduct, material = key

            fabric_code = material.default_code or ''
            # -----------------------------------------------------------------
            # Program part:
            # -----------------------------------------------------------------
            # todo choose the best program here?
            try:
                part = semiproduct.industria_rule_ids[0]
                part_id = part.id
                program_id = part.fabric_id.program_id.id
            except:
                part_id = False
                program_id = False

            # -----------------------------------------------------------------
            # Color part:
            # -----------------------------------------------------------------
            fabric = fabric_code[:6]
            color_part = fabric_code[6:]
            if color_part not in color_db:
                color_id = color_pool.create(cr, uid, {
                    'code': color_part,
                    'name': color_part,
                    'robot_id': robot_id,
                }, context=context)
                color_db[color_part] = color_pool.browse(
                    cr, uid, color_id, context=context)
            color = color_db[color_part]
            replace = color_db.get(color.replace)
            if replace:
                color = replace
            line_pool.create(cr, uid, {
                'industria_mrp_id': mrp_id,
                'part_id': part_id,
                'program_id': program_id,
                'product_id': semiproduct.id,
                'material_id': material.id,
                'fabric': fabric,
                'color': color.code,
                'sequence': color.sequence,
                'todo': todo,
                'detail': detail,
            }, context=context)
        return True

    # -------------------------------------------------------------------------
    # Workflow button:
    # -------------------------------------------------------------------------
    def wfk_confirmed(self, cr, uid, ids, context=None):
        """ Set as confirmed
        """
        return self.write(cr, uid, ids, {
            'state': 'confirmed',
        }, context=context)

    def wfk_pause(self, cr, uid, ids, context=None):
        """ Set as pause
        """
        return self.write(cr, uid, ids, {
            'state': 'pause',
        }, context=context)

    def wfk_done(self, cr, uid, ids, context=None):
        """ Set as done
        """
        return self.write(cr, uid, ids, {
            'state': 'done',
        }, context=context)

    def wfk_draft(self, cr, uid, ids, context=None):
        """ Set as draft
        """
        return self.write(cr, uid, ids, {
            'state': 'draft',
        }, context=context)

    _columns = {
        'date': fields.date(
            'Data', help='Data di creazione'),
        'robot_id': fields.many2one('industria.robot', 'Robot', required=True),
        # todo: how assign yet present semi-product?
        # 'picking': fields.many2one(
        # 'stock.picking', 'Documento di impegno', '')
        'state': fields.selection([
            ('draft', 'Bozza'),
            ('confirmed', 'Confermato'),
            ('pause', 'In pausa'),
            ('done', 'Fatto'),
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
    _order = 'program_id, sequence, fabric'
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

    def _get_product_program(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = [
                part.fabric_id.program_id.id for part in
                line.product_id.industria_rule_ids]
        return res

    _columns = {
        'industria_mrp_id': fields.many2one(
            'industria.mrp', 'MRP I4.0'),
        'material_id': fields.many2one(
            'product.product', 'Materiale'),
        'product_id': fields.many2one(
            'product.product', 'Semilavorato'),
        'part_id': fields.many2one(
            'industria.program.fabric.part', 'Regola'),
        'program_id': fields.many2one(
            'industria.program', 'Programma'),
        'program_ids': fields.function(
            _get_product_program, method=True,
            type='many2many', relation='industria.program',
            string='Programmi disponibili',
            ),
        'sequence': fields.integer('Ord.'),
        'fabric': fields.text('Tessuto', size=20),
        'color': fields.text('Colore', size=10),

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
