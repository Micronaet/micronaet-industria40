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
    _rec_name = 'name'

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

        # Cannot delete job if not draft:
        for job in industria_mrp.job_ids:
            if job.state == 'DRAFT':
                _logger.warning('Deleted %s job' % job.id)
                job_pool.unlink(cr, uid, [job.id], context=context)

        program_created = {}  # job, step, max layer available
        sequence = 0
        now = datetime.now()  # note used now manually!!
        for line in industria_mrp.line_ids:  # Sorted by program
            sequence += 1  # Sequence still progress for all program!
            program = line.program_id
            if not program:  # todo raise error?
                _logger.error('Line without program')
                continue
            robot = program.source_id
            database = robot.database_id
            part = line.part_id  # winner rule
            fabric_id = line.material_id.id
            product_id = line.product_id.id
            block = part.total  # total semi product in one program
            max_layer = robot.max_layer

            if not max_layer:
                raise osv.except_osv(
                    _('Errore setup'),
                    _('Non è stato impostato il numero massimo di strati '
                      'nel robot di taglio tessuto!'))

            if not block:
                raise osv.except_osv(
                    _('Errore setup'),
                    _('Nel programma sono stati inseriti dei semilavorati'
                      'senza indicare il numero totale di pezzi generati'))

            total = line.remain  # Total semi product to do

            # todo what to do with waste?
            extra_block = total % block > 0
            sp_total_layers = int(total / block) + (1 if extra_block else 0)

            # Total layers is total layer put in job will turn to 0:
            while sp_total_layers > 0:
                if program not in program_created:
                    _logger.warning(
                        'Create new job for cache, program: %s' % program.name)
                    now -= timedelta(seconds=1)
                    job_id = job_pool.create(cr, uid, {
                        'created_at': now.strftime(
                            DEFAULT_SERVER_DATETIME_FORMAT),
                        'source_id': robot.id,
                        'database_id': database.id,
                        'industria_mrp_id': industria_mrp_id,
                        'program_id': program.id,  # Always one so put in head!
                    }, context=context)

                    # todo create more step?
                    step_id = step_pool.create(cr, uid, {
                        'job_id': job_id,
                        'sequence': 1,
                        'program_id': program.id,
                    }, context=context)
                    # Save used data:
                    program_created[program] = [job_id, step_id, max_layer]

                # Check max number of layer for create new job!
                job_id, step_id, job_remain_layer = program_created[program]
                if sp_total_layers <= job_remain_layer:  # Available this job:
                    program_created[program][2] -= sp_total_layers
                    this_layer = sp_total_layers
                    sp_total_layers = 0  # Covered all, end loop
                    job_ended = False
                    _logger.warning('End layer with new job')

                else:
                    this_layer = job_remain_layer  # todo change if is small #
                    sp_total_layers -= job_remain_layer
                    job_ended = True
                    _logger.warning('Continue layer in this job')

                # -------------------------------------------------------------
                # Create layer (used for unload FABRIC)
                # -------------------------------------------------------------
                fabric_line_id = fabric_pool.create(cr, uid, {
                    'sequence': sequence,
                    'step_id': step_id,
                    'fabric_id': fabric_id,
                    'total': this_layer,
                    # related 'industria_mrp_id': industria_mrp_id,
                }, context=context)

                # -------------------------------------------------------------
                # Link product from program to fabric step:
                # -------------------------------------------------------------
                total_product = this_layer * block
                fabric_product_pool.create(cr, uid, {
                    'fabric_id': fabric_line_id,
                    'product_id': product_id,
                    'total': total_product,
                }, context=context)

                # todo add also extra semi product not used here (from program)
                # Some program has 2 different semi product maybe one is not
                # used

                if job_ended:
                    _logger.warning(
                        'Delete job from cache, '
                        'so new will created for program: %s' % program.name)
                    del(program_created[program])

        return True

    def generate_industria_mrp_line(self, cr, uid, ids, context=None):
        """ Generate lined from MRP production linked
        """
        color_pool = self.pool.get('industria.robot.color')
        line_pool = self.pool.get('industria.mrp.line')

        material_category = 'Tessuti'  # todo manage better

        # ---------------------------------------------------------------------
        # Load color
        # ---------------------------------------------------------------------
        color_db = {}
        color_ids = color_pool.search(cr, uid, [], context=context)
        for color in color_pool.browse(cr, uid, color_ids, context=context):
            color_db[color.code] = color

        # I40 MRP:
        mrp_id = ids[0]
        i40_mrp = self.browse(cr, uid, mrp_id, context=context)
        robot_id = i40_mrp.robot_id.id

        # Clean previous line:
        _logger.warning('Clean previous line')
        # todo clean line:
        line_ids = [l.id for l in i40_mrp.line_ids]
        line_pool.unlink(cr, uid, line_ids, context=context)

        # ---------------------------------------------------------------------
        # Collect new line from MRP list (and BOM):
        # ---------------------------------------------------------------------
        new_lines = {}
        _logger.warning('Generate new lines:')
        for mrp in i40_mrp.mrp_ids:
            for line in mrp.order_line_ids:
                todo = (
                    line.product_uom_qty -
                    # todo consider also maked?:
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

        # ---------------------------------------------------------------------
        # Generate line:
        # ---------------------------------------------------------------------
        _logger.warning('Generate new lines:')
        for key in new_lines:
            todo, detail = new_lines[key]
            semiproduct, material = key

            fabric_code = material.default_code or ''

            # -----------------------------------------------------------------
            # Assign Program:
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

    # todo remove:
    def _get_stock_move_ids(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for mrp in self.browse(cr, uid, ids, context=context):
            res[mrp.id] = [
                move.id for move in mrp.picking_id.move_lines]
        return res

    def name_get(self, cr, uid, ids, context=None):
        """ Better description
        """
        res = []
        for mrp in self.browse(cr, uid, ids, context=context):
            res.append((
                mrp.id,
                'Job %s (%s)' % (
                    mrp.date, mrp.name or ', '.join(
                        [m.name for m in mrp.mrp_ids]))
            ))
        return res

    _columns = {
        'name': fields.char(
            'Nome', help='Indicare per riconoscere meglio la lavorazione'),
        'date': fields.date(
            'Data', help='Data di creazione'),
        # todo remove not used:
        'picking_id': fields.many2one(
            'stock.picking', 'Documento scarico',
            ondelete='set null',
            help='Documento per scaricare subito i materiali assegnati alla '
                 'produzione attuale',
        ),
        # todo remove no more used:
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
    # todo remove:
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
        line_id = ids[0]
        line = self.browse(cr, uid, line_id, context=context)

        model_pool = self.pool.get('ir.model.data')
        view_id = model_pool.get_object_reference(
            cr, uid,
            'industria40_robot', 'industria_mrp_line_view_wizard_form')[1]

        product = line.product_id
        available_qty = product.mx_net_mrp_qty
        current_stock_qty = line.assigned
        remain_qty = line.remain
        # todo clean locked qty!

        new_bounded = min(available_qty, remain_qty)

        self.write(cr, uid, ids, {
            'new_bounded': new_bounded + current_stock_qty,
        }, context=context)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Dettaglio assegnazione magazzino'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': line_id,
            'res_model': 'industria.mrp.line',
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
            res[line.id] = {
                'program_id': line.part_id.fabric_id.program_id.id,  # todo save in part program
                'program_ids': [],
                'part_ids': [],
            }
            for part in line.product_id.industria_rule_ids:
                res[line.id]['part_ids'].append(part.id)
                res[line.id]['program_ids'].append(
                    part.fabric_id.program_id.id)
        return res

    def get_total_field_data(self, cr, uid, ids, fields, args, context=None):
        """ Calculate all total fields
        """
        job_product_pool = self.pool.get('industria.job.fabric.product')

        res = {}
        industria_cache = {}
        for line in self.browse(cr, uid, ids, context=context):
            industria_mrp_id = line.industria_mrp_id.id
            product_id = line.product_id.id  # Semi product

            # Cache unload data for production:
            if industria_mrp_id not in industria_cache:
                industria_cache[industria_mrp_id] = {}
                for unload in line.industria_mrp_id.unload_ids:
                    industria_cache[industria_mrp_id][unload.product_id.id] = \
                        unload.quantity

            total = line.todo  # A.
            assigned = line.assigned  # B.

            # Produced:
            produced = 0  # C. (used job data not stock picking?)
            job_product_ids = job_product_pool.search(cr, uid, [
                # todo related if slow procedure:
                ('fabric_id.step_id.job_id.industria_mrp_id', '=',
                 industria_mrp_id),
                ('fabric_id.step_id.job_id.state', '=',
                 'COMPLETED'),  # only done!
                ('product_id', '=', product_id),
            ], context=context)
            for job_product in job_product_pool.browse(
                    cr, uid, job_product_ids, context=context):
                produced += job_product.total  # todo check

            # Used in MRP
            used = industria_cache[industria_mrp_id].get(product_id, 0)

            # Total:
            linked = assigned + produced
            remain = total - linked
            bounded = linked # - used  # net bounded

            # Bounded quantity:
            if remain < 0:
                bounded -= remain  # todo check: Extra production goes in stock
            if used:
                bounded -= used
                bounded = max(0, bounded)

            res[line.id] = {
                'produced': produced,
                'remain': max(0, remain),
                'bounded': bounded,
                'used': used,
                # todo add line list m2m here?
            }
        return res

    # -------------------------------------------------------------------------
    # Wizard button event:
    # -------------------------------------------------------------------------
    def action_assign(self, cr, uid, ids, context=None):
        """ Event for button done
        """
        line = self.browse(cr, uid, ids, context=context)[0]
        assigned = line.new_bounded
        self.write(cr, uid, ids, {
            'assigned': assigned,
        }, context=context)
        return True  # {'type': 'ir.actions.act_window_close'}

    def _get_bounded_lines(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        assert len(ids) == 1, 'Dettagli disponibili solo un prodotto per volta'

        line_id = ids[0]
        line = self.browse(cr, uid, line_id, context=context)
        product_id = line.product_id.id
        product_pool = self.pool.get('product.product')
        bounded_ids = product_pool._get_bounded_lines(
            cr, uid, [product_id], [], {}, context=context)[product_id]

        res = {line_id: bounded_ids}
        return res

    _columns = {
        'stock_bounded_ids': fields.function(
            _get_bounded_lines, method=True, relation='industria.mrp.line',
            type='many2many', string='Impegni MRP'),
        'industria_mrp_id': fields.many2one(
            'industria.mrp', 'MRP I4.0', ondelete='cascade'),
        # todo remove, not used for assigned qty!
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
        # 'program_id': fields.many2one(
        #    'industria.program', 'Programma'),
        'program_id': fields.function(
            _get_product_program, method=True, multi=True, readonly=True,
            type='many2one', relation='industria.program',
            string='Programma',
            help='Programma selezionato in base alla regola scelta'
            ),
        'program_ids': fields.function(
            _get_product_program, method=True, multi=True,
            type='many2many', relation='industria.program',
            string='Programmi disponibili',
            ),
        'part_ids': fields.function(
            _get_product_program, method=True, multi=True,
            type='many2many', relation='industria.program.fabric.part',
            string='Regole',
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
        # ),

        'todo': fields.integer(
            string='Nominali', help='Totale come da produzioni collegate'),
        'assigned': fields.integer(
            string='Assegnati', help='Assegnati da magazzino manualmente'),
        'produced': fields.function(
            get_total_field_data, method=True,
            type='integer', multi=True,
            string='Prodotti', help='Fatti con i job di lavoro su taglio'),
        'remain': fields.function(
            get_total_field_data, method=True,
            type='integer', multi=True,
            string='Residui',
            help='Residui da produrre (calcolato da quelli da fare puliti da '
                 'quelli fatti o assegnati'),
        'used': fields.function(
            get_total_field_data, method=True,
            type='integer', multi=True,
            string='Usato',
            help='Utilizzati dalle produzioni collegate alla attuale commessa'
            ),
        'bounded': fields.function(
            get_total_field_data, method=True,
            type='integer', multi=True,
            string='Collegati',
            help='Calcolo dei semilavorati assegnati da magazzino o prodotti '
                 'per una determinata produzione'),
        'new_bounded': fields.integer('Nuova proposta')
    }

    _defaults = {
        'state': lambda *x: 'draft',
    }


class IndustriaJobFabric(orm.Model):
    """ Model name: Job Fabric relation
    """
    _inherit = 'industria.job.fabric'

    # _columns = {
    #    # todo needed? (if only in one filter could be removed!)
    #    'industria_mrp_id': fields.related(
    #        'step_id', 'industria_mrp_id',
    #        type='many2one', relation='industria.mrp',
    #        string='MRP Industria 4.0', store=True),
    # }


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


# todo remove, not used for assigned qty:
class StockMove(orm.Model):
    """ Model name: Link move to Industria MRP
    """
    _inherit = 'stock.move'

    _columns = {
        'generator_job_id': fields.many2one(
            'industria.job', 'Job generatore',
            help='Job che ha generato il movimento di magazzino'),
    }


class StockPicking(orm.Model):
    """ Model name: Link picking to Industria MRP
    """
    _inherit = 'stock.picking'

    def delete_picking_i40(self, cr, uid, ids, context=None):
        """ Delete picking
        """
        stock_pool = self.pool.get('stock.move')
        picking_id = ids[0]
        stock_ids = stock_pool.search(cr, uid, [
            ('picking_id', '=', picking_id),
        ], context=context)
        stock_pool.write(cr, uid, stock_ids, {
            'state': 'cancel',
        }, context=context)
        stock_pool.unlink(cr, uid, stock_ids, context=context)

        return self.unlink(cr, uid, ids, context=context)

    _columns = {
        'industria_mrp_id': fields.many2one(
            'industria.mrp', 'Produzione I40',
            help='Collegamento del picking al suo documento di '
                 'produzione principale'),
        'generator_job_id': fields.many2one(
            'industria.job', 'Job generatore',
            help='Job che ha generato il movimento di magazzino',
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


class IndustriaMrpUnload(orm.Model):
    """ Model name: Industria 4.0 MRP unload
    """

    _name = 'industria.mrp.unload'
    _description = 'Industria 4.0 MRP unload'
    _rec_name = 'product_id'

    _columns = {
        'industria_mrp_id': fields.many2one(
            'industria.mrp', 'Produzione I40', ondelete='cascade'),
        'product_id': fields.many2one(
            'product.product', 'Semilavorato', ondelete='set null'),
        'quantity': fields.integer('Scarico produzione'),
    }


class IndustriaMrpInherit(orm.Model):
    """ Model name: MrpProductionOven
    """

    _inherit = 'industria.mrp'

    _columns = {
        'unload_ids': fields.one2many(
            'industria.mrp.unload', 'industria_mrp_id', 'Scarichi',
            help='Scarichi dai bloccaggi di produzione (ricordare che le'
                 'operazioni di aggiornamento dei dati sono giornaliere,'
                 'eventualmente forzarle prima di usare il dato)',
        ),
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
        'picking_ids': fields.one2many(
            'stock.picking', 'industria_mrp_id', 'Picking',
            help='Sviluppo picking per semilavorati da passare alla '
                 'macchina',
        ),
    }


class ProductProductIndustriaJob(orm.Model):
    """ Model name: Product
    """
    _inherit = 'product.product'

    def _get_bounded_lines(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        line_pool = self.pool.get('industria.mrp.line')
        assert len(ids) == 1, 'Dettagli disponibili solo un prodotto per volta'

        product_id = ids[0]
        res = {product_id: []}

        # Extract active linked lines:
        line_ids = line_pool.search(cr, uid, [
            ('product_id', '=', product_id),
        ], context=context)
        bounded_ids = res[product_id]
        for line in line_pool.browse(cr, uid, line_ids, context=context):
            bounded = line.bounded
            if bounded > 0:  # Only bounded fields
                # todo manage with a boolean for fast search when close line?
                bounded_ids.append(line.id)
        return res

    _columns = {
        'stock_bounded_ids': fields.function(
            _get_bounded_lines, method=True, relation='industria.mrp.line',
            type='many2many', string='Impegni MRP',
            store=False),
        'industria_rule_ids': fields.many2many(
            'industria.program.fabric.part', 'product_industria_part_rel',
            'product_id', 'part_id',
            'Regola assegnazione'),
        }
