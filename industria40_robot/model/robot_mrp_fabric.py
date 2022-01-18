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


class IndustriaRobot(orm.Model):
    """ Model name: Industria 4.0 MRP
    """

    _inherit = 'industria.robot'

    _columns = {
        'color_ids': fields.one2many(
            'industria.robot.color', 'robot_id', 'Colori'),
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
        fabric_product_pool = self.pool.get('industria.job.fabric.product')

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
            fabric_id = line.material_id.id
            product_id = line.product_id.id
            block = part.total
            if not block:
                raise osv.except_osv(
                    _('Errore setup'),
                    _('Nel programma sono stati inseriti dei semilavorati'
                      'senza indicare il numero totale di pezzi generati'))

            total = line.todo  # todo use line.remain

            # todo what to do with waste?
            extra_block = total % block > 0
            total_layers = int(total / block) + (1 if extra_block else 0)
            total_product = total + (block if extra_block else 0)

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
                # todo create more step?
                step_id = step_pool.create(cr, uid, {
                    'job_id': job_id,
                    'sequence': 1,
                    'program_id': program.id,
                }, context=context)
                program_created[program] = job_id, step_id

            # -----------------------------------------------------------------
            # Create layer (used for unload fabric)
            # -----------------------------------------------------------------
            job_id, step_id = program_created[program]
            fabric_pool.create(cr, uid, {
                'sequence': sequence,
                'step_id': step_id,
                'fabric_id': fabric_id,
                'total': total_layers,
            }, context=context)

            # -----------------------------------------------------------------
            # Link product from program to fabric step:
            # -----------------------------------------------------------------
            fabric_product_pool.create(cr, uid, {
                'fabric_id': fabric_id,
                'product_id': product_id,
                'total': total_product,
            }, context=context)
            # todo add also extra semi product not used here (from program)!

        return True

    def generate_industria_mrp_line(self, cr, uid, ids, context=None):
        """ Generate lined from MRP production linked
        """
        color_pool = self.pool.get('industria.robot.color')
        line_pool = self.pool.get('industria.mrp.line')

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
        # todo clean line:
        line_ids = [l.id for l in i40_mrp.line_ids]
        line_pool.unlink(cr, uid, line_ids, context=context)

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

    def _get_stock_move_ids(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for mrp in self.browse(cr, uid, ids, context=context):
            res[mrp.id] = [
                move.id for move in mrp.picking_id.move_lines]
        return res

    _columns = {
        'date': fields.date(
            'Data', help='Data di creazione'),
        'picking_id': fields.many2one(
            'stock.picking', 'Documento scarico',
            ondelete='set null',
            help='Documento per scaricare subito i materiali assegnati alla '
                 'produzione attuale',
        ),
        'stock_move_ids': fields.function(
            _get_stock_move_ids, method=True,
            type='many2many', relation='stock.move',
            string='Assegnati da magazzino',
            help='Elenco movimenti di scarico assegnati a magazzino a questa'
                 'produzione'
        ),

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

    # Stock operation:
    def industria_get_movement(self, cr, uid, ids, qty, context=None):
        """ Create or return picking
        """
        company_pool = self.pool.get('res.company')
        picking_pool = self.pool.get('stock.picking')
        move_pool = self.pool.get('stock.move')
        i40_mrp_pool = self.pool.get('industria.mrp')

        company_proxy = company_pool._get_company_browse(
            cr, uid, context=context)

        # ---------------------------------------------------------------------
        # Picking:
        # ---------------------------------------------------------------------
        i40_line_id = ids[0]
        i40_line = self.browse(cr, uid, i40_line_id, context=context)
        i40_mrp = i40_line.industria_mrp_id
        i40_mrp_id = i40_mrp.id

        product = i40_line.product_id
        sl_type = company_proxy.sl_mrp_lavoration_id
        sl_type_id = sl_type.id
        location_src_id = sl_type.default_location_src_id.id
        location_dest_id = sl_type.default_location_dest_id.id

        if i40_mrp.picking_id:
            picking_id = i40_mrp.picking_id
        else:
            date = i40_mrp.date
            origin = 'I40 MRP del %s' % date
            picking_id = picking_pool.create(cr, uid, {
                # 'dep_mode': 'workshop',  # Always
                'origin': origin,
                # 'partner_id':
                'date': date,
                'min_date': date,
                'note': 'Abbinata in automatico a I4.0 MRP',
                'state': 'done',  # yet complete!
                'picking_type_id': sl_type_id,
                # 'is_mrp_lavoration': True,
                # 'location_id': location_id,
            }, context=context)
            i40_mrp_pool.write(cr, uid, [i40_mrp_id], {
                'picking_id': picking_id,
            }, context=context)

        stock_move_id = i40_line.stock_move_id
        if stock_move_id:
            move_pool.write(cr, uid, [stock_move_id], {
                'product_uom_qty': qty,
            }, context=context)
        else:
            onchange = move_pool.onchange_product_id(
                cr, uid, False, product.id, location_src_id,
                location_dest_id, False)  # no partner
            move_data = onchange.get('value', {})
            move_data.update({
                'picking_id': picking_id,
                'product_id': product.id,
                'product_uom_qty': qty,
                'location_id': location_src_id,
                'location_dest_id': location_dest_id,
                'state': 'done',
            })
            stock_move_id = move_pool.create(
                cr, uid, move_data, context=context)
            self.write(cr, uid, [i40_line_id], {
                'stock_move_id': stock_move_id,
            }, context=context)
        return True

    def assign_stock_quantity(self, cr, uid, ids, context=None):
        """ Assign document wizard
        """
        wizard_pool = self.pool.get('industria.assign.stock.wizard')
        line_id = ids[0]
        line = self.browse(cr, uid, line_id, context=context)
        view_id = False

        product = line.product_id
        total_qty = line.todo
        produced_qty = 0  # todo:
        available_qty = product.mx_net_mrp_qty
        locked_qty = line.stock_move_id.product_uom_qty
        remain_qty = max(0, total_qty - produced_qty - locked_qty)
        new_qty = min(available_qty, remain_qty)
        comment = ''
        if not new_qty:
            comment = _(
                'Non ci sono le disponibilità per assegnare il magazzino'
                'oppure è già tutto assegnato / prodotto')
        elif new_qty < locked_qty:
            comment = _(
                'E\' già assegnata la massima quantità disponibile per '
                'questo prodotto')
        data = {
            'industria_line_id': line_id,
            'available_qty': available_qty,
            'produced_qty': produced_qty,
            'locked_qty': locked_qty,
            'remain_qty': remain_qty,
            'total_qty': total_qty,
            'new_qty': new_qty,
            'comment': comment,
        }
        wizard_id = wizard_pool.create(cr, uid, data, context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Dettaglio assegnazione magazzino'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': wizard_id,
            'res_model': 'industria.assign.stock.wizard',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'domain': [],
            'context': context,
            'target': 'new',
            'nodestroy': False,
            }

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

    def get_total_field_data(self, cr, uid, ids, fields, args, context=None):
        """ Calculate all total fields
        """
        job_fabric_pool = self.pool.get('industria.job.fabric')

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            industria_mrp_id = line.industria_mrp_id.id
            product_id = line.product_id.id  # Semi product
            total = line.todo  # A.
            assigned = line.stock_move_id.product_uom_qty  # B.

            # Produced:
            produced = 0  # C. todo
            job_fabric_ids = job_fabric_pool.search(cr, uid, [
                # ('industria_mrp_id', '=', industria_mrp_id),
                # ('product_id', '=', product_id),
            ], context=context)
            for jf in job_fabric_pool.browse(
                    cr, uid, job_fabric_ids, context=context):
                produced += jf.total  # todo check

            # Total:
            bounded = assigned + produced  # E
            remain = total - bounded  # D (A-(B+C))  >> B+C=E
            # Bounded quantity:
            if remain < 0:
                bounded -= remain  # Extra production goes in stock

            res[line.id] = {
                'assigned': assigned,
                'produced': produced,
                'remain': remain,
                'bounded': bounded,
                # todo add line list m2m here?
            }
        return res

    _columns = {
        'industria_mrp_id': fields.many2one(
            'industria.mrp', 'MRP I4.0', ondelete='cascade'),
        'stock_move_id': fields.many2one(
            'stock.move', 'Movimenti assegnati', ondelete='set null',
            help='Collegamento al movimento che scarica gli impegni per questo'
                 'semilavorato'),
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

        # todo remove?
        # 'program_ids': fields.function(
        #    get_total_field_data, method=True,
        #    type='many2many', relation='industria.program',
        #    string='Programmi disponibili',
        #),

        'todo': fields.integer(
            string='Nominali', help='Totale come da produzioni collegate'),
        'assigned': fields.function(
            get_total_field_data, method=True,
            type='float', multi=True,
            string='Assegnati', help='Assegnati da magazzino'),
        'produced': fields.function(
            get_total_field_data, method=True,
            type='float', multi=True,
            string='Prodotti', help='Fatti con i job di lavoro '),
        'remain': fields.function(
            get_total_field_data, method=True,
            type='float', multi=True,
            string='Residui',
            help='Residui da produrre (calcolato da quelli da fare puliti da '
                 'quelli fatti o assegnati'),
        'bounded': fields.function(
            get_total_field_data, method=True,
            type='float', multi=True,
            string='Collegati',
            help='Calcolo dei semilavorati assegnati da magazzino o prodotti '
                 'per una determinata produzione'),
    }

    _defaults = {
        'state': lambda *x: 'draft',
    }


class IndustriaJobFabric(orm.Model):
    """ Model name: Job Fabric relation
    """
    _inherit = 'industria.job.fabric'

    #_columns = {
    #    'industria_mrp_id': fields.related(
    #        'step_id', 'industria_mrp_id',
    #        type='many2one', relation='industria.mrp',
    #        string='MRP Industria 4.0', store=True),
    #}


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
            'industria.mrp', 'Produzione I40', ondelete='set null',
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
            ondelete='cascade',
            help='Sviluppo produzioni per semilavorati da passare alla '
                 'macchina',
        ),
    }
