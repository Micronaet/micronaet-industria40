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
import requests
import json
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

    def explode_oven_job_per_color_forced(self, cr, uid, ids, context=None):
        """ Force all order
        """
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['force_all'] = True
        return self.explode_oven_job_per_color(cr, uid, ids, context=ctx)

    def explode_oven_job_per_color(self, cr, uid, ids, context=None):
        """ Generate Oven job
            context parameter: force_all >> Use all ordered not remain
        """
        if context is None:
            context = {}
        force_all = context.get('force_all')

        # Pool used:
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
                if not color_code:
                    continue

                # -------------------------------------------------------------
                # Get remain (2 cases):
                # -------------------------------------------------------------
                # 1. Case force:
                if force_all:
                    remain = line.product_uom_qty
                else:
                    if line.mx_closed:
                        continue  # neutral color or closed line (jump)
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
                        'line_id': line.id,
                        'product_id': line.product_id.id,
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
    _order = 'color_code, parent_code'
    _rec_name = 'parent_code'

    def unlink_line(self, cr, uid, ids, context=None):
        """ Unlink line from job
        """
        return self.write(cr, uid, ids, {
            'job_id': False,
        }, context=context)

    def generate_oven_job(self, cr, uid, ids, context=None):
        """ Generate Oven job
        """
        if context is None:
            context = {}
        record = self.browse(cr, uid, ids[0], context=context)
        ctx = context.copy()
        ctx['force_color'] = record.color_code
        return self.generate_oven_job_all(cr, uid, ids, context=ctx)

    def generate_oven_job_all(self, cr, uid, ids, context=None):
        """ Generate Oven job
            Parameter for single color: force_color
        """
        job_pool = self.pool.get('industria.job')
        robot_pool = self.pool.get('industria.robot')
        program_pool = self.pool.get('industria.program')

        robot_ids = robot_pool.search(cr, uid, [
            ('code', '=', 'FORN01'),
        ], context=context)
        if not robot_ids:
            raise osv.except_osv(
                _('Errore recupero forno'),
                _('Non trovato robot - forno codice FORN01'),
                )

        robot = robot_pool.browse(cr, uid, robot_ids[0], context=context)
        robot_id = robot.id
        database_id = robot.database_id.id

        program_ids = program_pool.search(cr, uid, [
            ('source_id.code', '=', 'FORN01'),
            ('code', '=', 'FORNBASE'),
        ], context=context)
        if not program_ids:
            raise osv.except_osv(
                _('Errore programma forno'),
                _('Non trovato il programma unico per i robot tipo forno '
                  '(o non esiste il codice FORNBASE nel programma)'),
                )
        program_id = program_ids[0]  # todo Take the first for now

        # Select with dynamic domain:
        if context is None:
            context = {}
        force_color = context.get('force_color')
        domain = [('job_id', '=', False)]  # pending not linked
        if force_color:
            domain.append(('color_code', '=', force_color))
        record_ids = self.search(cr, uid, domain, context=context)

        # Collect data x color:
        jobs_created = {}
        for record in self.browse(cr, uid, record_ids, context=context):
            color = record.color_code
            # if not color:
            #    _logger.error('Color not present, jumped')
            #    continue
            if color not in jobs_created:
                jobs_created[color] = job_pool.create(cr, uid, {
                    'database_id': database_id,
                    'source_id': robot_id,
                    'program_id': program_id,
                    'color': color,
                    # 'created_at':
                    # 'force_name': ,
                    # 'label': 1,
                    # 'state': 'draft',
                }, context=context)

            # Link pre-line to job:
            self.write(cr, uid, [record.id], {
                'job_id': jobs_created[color],
            }, context=context)

        # Explode lines in job detail (simulate button press):
        job_ids = []
        for color in jobs_created:
            job_id = jobs_created[color]
            job_ids.append(job_id)
            job_pool.explode_oven_preload_detail(
                cr, uid, [job_id], context=context)

        # Return view:
        model_pool = self.pool.get('ir.model.data')
        form_view_id = model_pool.get_object_reference(
            cr, uid, 'industria40_base', 'view_industria_job_opcua_form',
        )[1]
        tree_view_id = False
        ctx = context.copy()
        ctx.update({
            'search_default_state_draft': True,
            'default_state': 'DRAFT',
        })

        if len(job_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Job generati'),
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': job_ids[0],
                'res_model': 'industria.job',
                'view_id': form_view_id,
                'views': [(form_view_id, 'form'), (tree_view_id, 'tree')],
                'domain': [],
                'context': ctx,
                'target': 'current',
                'nodestroy': False,
                }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Job generati'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                # 'res_id': 1,
                'res_model': 'industria.job',
                'view_id': tree_view_id,
                'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
                'domain': [('id', 'in', job_ids)],
                'context': ctx,
                'target': 'current',
                'nodestroy': False,
            }

    _columns = {
        'send': fields.boolean('Da spedire'),
        'parent_code': fields.char('Codice padre', size=5, required=True),
        'color_code': fields.char('Codice colore', size=5, required=True),
        'total': fields.integer('Totali'),
        'partial': fields.integer(
            'Parziali', help='Pezzi parziali da mandare in lavorazione'),
        'from_date': fields.date('Dalla data'),
        'to_date': fields.date('Alla data'),
        'mrp_id': fields.many2one(
            'mrp.production', 'Produzione', ondelete='set null'),
        'line_id': fields.many2one(
            'sale.order.line', 'Riga OC', ondelete='set null'),
        'job_id': fields.many2one(
            'industria.job', 'Job', ondelete='set null'),
        'product_id': fields.many2one(
            'product.product', 'Prodotto', ondelete='set null'),
    }


class MrpProductionOvenInherit(orm.Model):
    """ Model name: MrpProductionOven
    """

    _inherit = 'mrp.production'

    _columns = {
        'oven_pre_job_ids': fields.one2many(
            'mrp.production.oven.selected', 'mrp_id',
            'Pre-Job forno'),
    }


class MrpProductionOvenCabin(orm.Model):
    """ Wizard name: class Mrp Production Oven Cabin
    """
    _name = 'mrp.production.oven.cabin'
    _description = 'Oven cabin'
    _rec_name = 'creation_date'

    _columns = {
        'job_id': fields.many2one('industria.job', 'Job'),
        'sql_id': fields.integer('ID SQL'),

        'enterprise_code': fields.char('Codice impianto', size=6),
        'company_code': fields.char('Codice sede', size=6),

        'creation_date': fields.datetime('Data creazione'),

        'paused': fields.boolean('In pausa'),
        'pause_duration': fields.float('Tot. pausa ore', digits=(10, 3)),

        'changing': fields.boolean('In cambio colore'),
        'duration_change': fields.float(
            'Durata cambio colore', digits=(10, 3)),
        'total_change': fields.integer('Tot. cambi colore'),

        'speed_chain': fields.char('Velocità catena', size=45),

        'duration_chain_pause': fields.float(
            'Durata pausa catena (ore)', digits=(10, 3)),
        'duration_chain_work': fields.float(
            'Durata marcia catena (ore)', digits=(10, 3)),

        'duration_nozzle_11': fields.float(
            'Tempo pistola 11 (ore)', digits=(10, 3)),
        'duration_nozzle_12': fields.float(
            'Tempo pistola 12 (ore)', digits=(10, 3)),
        'duration_nozzle_13': fields.float(
            'Tempo pistola 13 (ore)', digits=(10, 3)),
        'duration_nozzle_14': fields.float(
            'Tempo pistola 14 (ore)', digits=(10, 3)),
        'duration_nozzle_15': fields.float(
            'Tempo pistola 15 (ore)', digits=(10, 3)),
        'duration_nozzle_16': fields.float(
            'Tempo pistola 17 (ore)', digits=(10, 3)),
        'duration_nozzle_21': fields.float(
            'Tempo pistola 21 (ore)', digits=(10, 3)),
        'duration_nozzle_22': fields.float(
            'Tempo pistola 22 (ore)', digits=(10, 3)),
        'duration_nozzle_23': fields.float(
            'Tempo pistola 23 (ore)', digits=(10, 3)),
        'duration_nozzle_24': fields.float(
            'Tempo pistola 24 (ore)', digits=(10, 3)),
        'duration_nozzle_25': fields.float(
            'Tempo pistola 25 (ore)', digits=(10, 3)),

        'record_date': fields.datetime('Data registrazione'),

        'color_code': fields.char('Codice colore', size=45),
        'color_description': fields.char('Descrizione colore', size=45),

        'powder': fields.integer('Polvere consumata (Kg.)'),
        'comment': fields.char('Commento operatore', size=100),

        'job_code': fields.integer('Codice Job'),
        'job_year': fields.integer('Anno Job'),

        'mode': fields.selection([
            ('I', 'Inizio'),
            ('M', 'Monitor'),
            ('F', 'Fine'),
            ], 'Tipo')
        }


class IndustriaJob(orm.Model):
    """ Model name: Job relation
    """
    _inherit = 'industria.job'

    # Statistic function:
    def load_all_statistics(self, cr, uid, ids, context=None):
        """ Load statistic for this jobs
            Button mode event  but could be used from scheduled Job
        """
        database_pool = self.pool.get('industria.database')
        # Search oven cabin job passed and generate statistics
        # Update it not in closed state

        # 1. Search all job_id in statistics
        jobs = self.browse(cr, uid, ids, context=context)
        if not jobs:
            return False

        database = jobs[0].database_id
        cabin_call = database_pool.get_flask_sql_call(
                cr, uid, database, context=context)
        if not cabin_call:
            _logger.error('Cabin not ready!')
            return False

        # 2. Create or update statistic oven job
        url, headers, payload = cabin_call

        # Read all Job selected data:
        query = 'SELECT * FROM SIIMP00F WHERE SIIMPANN in (%s);' % (
            ', '.join([str(r) for r in ids]), )
        payload['params']['command'] = 'mysql_select'
        payload['params']['query'] = query

        response = requests.post(
            url, headers=headers, data=json.dumps(payload))
        response_json = response.json()
        if not response_json['success']:
            _logger.error(
                'Error calling Oven cabin: %s!' %
                response_json['reply']['error'])

        # 3. Update / Create statistic records:
        return True

        records = response_json['reply'].get('record')
        # todo part to be test when there's data on robot

        return True

    def explode_oven_preload_detail(self, cr, uid, ids, context=None):
        """ Generate job detail for product items in preproduction lines
        """
        job_product_pool = self.pool.get('industria.job.product')
        product_pool = self.pool.get('product.product')

        job_id = ids[0]

        # Clean previous items:
        self.write(cr, uid, [job_id], {
            'product_ids': [(6, 0, [])],
        }, context=context)

        job = \
            self.browse(cr, uid, job_id, context=context)
        product_detail = {}
        color = job.color
        robot_id = job.source_id.id
        for preline in job.oven_pre_job_ids:
            product = preline.product_id
            total = preline.total   # todo use partial?

            if product in product_detail:
                product_detail[product] += total
            else:
                product_detail[product] = total

        compact_product = {}
        # todo manage compact mode on job?
        for product in product_detail:
            total = product_detail[product]
            # Search component to oven:
            default_code = product.default_code or ''
            has_color = default_code[6:8].strip()
            if not has_color:
                _logger.error('Product %s no need oven' % default_code)
                continue
            for bom in product.dynamic_bom_line_ids:
                # if bom.category_id.need_oven:
                if bom.has_oven:  # dynamic bom module!
                    component_total = total * bom.product_qty
                    raw_component = bom.product_id
                    if raw_component not in compact_product:
                        compact_product[raw_component] = 0
                    compact_product[raw_component] += component_total

        for raw_component in compact_product:
            component_total = compact_product[raw_component]

            color_component_id = product_pool.get_oven_component_colored(
                cr, uid, raw_component, color, robot_id, context=context)
            # todo component colored 1-1 relation (if more than one need loop)
            # ex. with color powder

            # Generate line for every component:
            job_product_pool.create(cr, uid, {
                'job_id': job_id,
                'product_id': color_component_id,
                'piece': component_total,
            }, context=context)
        return True

    def _get_oven_program_id(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        display_pool = self.pool.get('industria.production')
        display_ids = display_pool.search(cr, uid, [
            ('job_id', '!=', False),
        ], context=context)
        display_db = {}
        for display in display_pool.browse(
                cr, uid, display_ids, context=context):
            display_db[display.job_id.id] = display.id

        res = {}
        for job_id in ids:
            res[job_id] = display_db.get(job_id)
        return res

    def button_clean_production(self, cr, uid, ids, context=None):
        """ Remove display program
        """
        assert len(ids) == 1, 'Svincolare solo un prodotto per volta!'

        display_pool = self.pool.get('industria.production')
        job = self.browse(cr, uid, ids, context=context)[0]

        display_id = job.oven_program_id.id
        if display_id:
            return display_pool.button_clean_production(
                cr, uid, [display_id], context=context)
        return False

    _columns = {
        'cabin_state_id': fields.many2one(
            'mrp.production.oven.cabin', 'Statistica cabina',
            help='Quando viene iniziato il lavoro vengono caricati i dati'
                 'statistici generati dalla cabina di verniciatura che '
                 'vengono tenuti aggiornati nel record abbinato al Job '
                 'di lavoro'
        ),
        'oven_program_id': fields.function(
            _get_oven_program_id, method=True,
            type='many2one', string='Programma a display',
            relation='industria.production', store=False,
            help='Programma a display sul forno industriale',
            ),

        'oven_pre_job_ids': fields.one2many(
            'mrp.production.oven.selected', 'job_id',
            'Pre-Job forno'),
    }


class MrpBomStructureCategory(orm.Model):
    """ Model name: BOM Category
    """
    _inherit = 'mrp.bom.structure.category'

    _columns = {
        # todo no more used:
        'need_oven': fields.boolean('Necessita verniciatura'),
        'need_fabric': fields.boolean('Necessita taglio tessuto'),
    }
