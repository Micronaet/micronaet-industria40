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
import shutil
import logging
import requests
import json
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp.tools.translate import _
from openerp.tools import (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_DATETIME_FORMAT,
    DATETIME_FORMATS_MAP,
    float_compare,
    )

_logger = logging.getLogger(__name__)


class IndustriaProduction(orm.Model):
    """ Model name: Industria Program
    """

    _name = 'industria.production'
    _description = 'Industria Production'
    _rec_name = 'name'
    _order = 'ref'

    def button_clean_production(self, cr, uid, ids, context=None):
        """ Clean job
        """
        job_pool = self.pool.get('industria.job')
        database_pool = self.pool.get('industria.database')
        production = self.browse(cr, uid, ids, context=context)[0]

        # Draft the job:
        job = production.job_id
        job_id = job.id
        if job_id:
            job_pool.write(cr, uid, [job_id], {
                'state': 'DRAFT',
            }, context=context)

        # Clean the Oven Box:
        database_pool.clean_flask_mysql_job(cr, uid, job, context=context)

        # Clean the display:
        return database_pool.clean_opcua_job(
            cr, uid, production.source_id, production.ref, context=context)

    def button_check_status_production_from_robot(
            self, cr, uid, ids, context=None):
        """ Check status for this production
        """
        database_pool = self.pool.get('industria.database')
        job_pool = self.pool.get('industria.job')

        # 1. Update status from robot:
        self.button_load_production_from_robot(cr, uid, ids, context=context)

        # 2. Load updated production:
        production = self.browse(cr, uid, ids, context=context)[0]

        # 3. Clean if job not present
        job = production.job_id
        if not job:
            _logger.error('No job linked, clean!')
            return self.button_clean_production(cr, uid, ids, context=context)

        # 4. Close if completed:
        if not production.is_completed:
            _logger.info('No need to close job!')
            return False

        job_pool.write(cr, uid, [job.id], {
            'duration': production.duration,  # Minute
            'duration_stop': production.stop_duration,  # Minute
            'duration_change': production.change_duration / 60.0,  # Second

            'created_at': production.start,
            'ended_at': production.stop,

            'state': 'COMPLETED',
        }, context=context)

        return self.button_clean_production(cr, uid, ids, context=context)

    def button_load_production_from_robot(self, cr, uid, ids, context=None):
        """ Update only this, force robot call passing ref and job_id
        """
        source_pool = self.pool.get('industria.robot')
        if context is None:
            context = {}
        production = self.browse(cr, uid, ids, context=context)[0]
        context_forced = context.copy()
        context_forced['reload_only_ref'] = production.ref
        context_forced['force_job_id'] = production.job_id.id

        return source_pool.button_load_production_from_robot(
            cr, uid, [production.source_id.id], context=context_forced)

    def button_send_manual_job(self, cr, uid, ids, context=None):
        """ Send manual job
        """
        # todo remove duplicated:
        def get_value(parameter):
            value = parameter.value
            out_type = parameter.opcua_id.type
            if out_type == 'float':
                return float(value.replace(',', '.')) or 0.0
            elif out_type == 'integer':
                return int(value) or 0
            else:
                return str(value or '')

        def get_ascii(value):
            res = ''
            for c in value:
                if ord(c) < 127:
                    res += c
                else:
                    res += '.'
            return str(res)

        if context is None:
            context = {}

        database_pool = self.pool.get('industria.database')
        production_pool = self.pool.get('industria.production')
        source_pool = self.pool.get('industria.robot')

        robot_ids = source_pool.search(cr, uid, [
            ('code', '=', 'FORN01'),
        ], context=context)
        if not robot_ids:  # todo use first not correct!
            raise osv.except_osv(
                _('Errore forno'),
                _('Trovare un Robot codice: FORN01'))

        source = source_pool.browse(cr, uid, robot_ids, context=context)[0]
        database = source.database_id
        if not source.program_ids:
            raise osv.except_osv(
                _('Errore forno'),
                _('Non trovati programmmi nel forno'))
        program = source.program_ids[0]  # todo use first (not correct)

        # Send to robot:
        robot = database_pool.get_robot(database)
        mask = source.opcua_mask

        # Get free program:
        production_id = ids[0]  # Current is selected program
        production = production_pool.browse(
                cr, uid, production_id, context=context)
        opcua_ref = production.ref

        if not opcua_ref:
            raise osv.except_osv(
                _('Errore commessa'),
                _('Impossibile creare commesse, il numero massimo è stato '
                  'raggiunto, chiuderne qualcuna e riprovare'))

        # Program parameter:
        for parameter in program.parameter_ids:
            command_text = get_ascii(mask % (
                parameter.opcua_id.name,
                opcua_ref
            ))
            _logger.info('OPCUA get: %s' % command_text)
            database_pool.set_data_value(
                robot,
                command_text,
                get_value(parameter),
            )

        # Header parameter:
        manual_job = production.manual_job
        manual_part = manual_job.split()
        lot = manual_part[0]
        color = ' '.join(manual_part[1:])
        database_pool.set_data_value(
            robot,
            mask % ('Commessa', opcua_ref),
            get_ascii(lot),
        )
        database_pool.set_data_value(
            robot,
            mask % ('Colore', opcua_ref),
            get_ascii(color),
        )

        # Reload this ref production (link to this job_id):
        context_forced = context.copy()
        context_forced['reload_only_ref'] = opcua_ref
        context_forced['force_job_id'] = ids[0]

        source_pool.button_load_production_from_robot(cr, uid, [
            source.id,
        ], context=context_forced)

        _logger.info('Send data to robot...')

        # todo
        # try:
        #     robot.disconnect()
        # except:
        #     _logger.error('Error disconnecting robot OPCUA!\n{}'.format(
        #         sys.exc_info(),
        #     ))
        return self.write(cr, uid, ids, {
            'state': 'RUNNING',
        }, context=context)

    _columns = {
        'source_id': fields.many2one('industria.robot', 'Robot'),
        'job_id': fields.many2one('industria.job', 'Job'),
        'ref': fields.integer('Rif.'),
        'name': fields.char('Commessa', size=30),
        'manual_job': fields.char('Job manuale', size=50),
        'temperature': fields.char('Temperatura', size=5),
        'speed': fields.char('Velocità', size=5),
        'color': fields.char('Colore', size=20),
        'start': fields.datetime('Inizio'),
        'stop': fields.datetime('Fine'),
        'duration': fields.integer('Durata'),
        'stop_duration': fields.integer('Durata fermo'),
        'change_duration': fields.integer('Durata cambio colore'),

        'is_working': fields.boolean('In lavorazione'),
        'is_completed': fields.boolean('Completata'),
        'is_live': fields.boolean('Live'),
    }


class IndustriaDatabase(orm.Model):
    """ Model name: Industria Database
    """
    _name = 'industria.database'
    _description = 'Database PC'
    _rec_name = 'name'
    _order = 'name'

    # -------------------------------------------------------------------------
    # ROBOT Interface:
    # -------------------------------------------------------------------------
    # Format function:
    # def extract_integer(self, field):
    #    """ Extract date from OPCUA record
    #    """
    #    return field == 'true'

    def extract_boolean(self, field_value):
        """ Extract date from OPCUA record
        """
        return field_value  # == 'true'

    def extract_date(self, record, mode='Inizio'):
        """ Extract date from OPCUA record
            mode: 'Inizio', 'Fine'
        """
        year = record['%sAnno' % mode]
        if not year or year == '0':  # Check all?
            return False

        return '%s-%s-%s %s:%s:00' % (
            year,
            record['%sMese' % mode],
            record['%sGiorno' % mode],
            record['%sOra' % mode],
            record['%sMinuto' % mode],
        )

    def get_robot(self, database):
        """ Return robot to use
        """
        import opcua

        # Create and connect as client:
        uri = u'opc.tcp://%s:%s' % (database.opcua_ip, database.opcua_port)
        robot = opcua.Client(uri)
        try:
            robot.connect()
            return robot
        except:
            raise osv.except_osv(
                _('Errore connessione'),
                _('Dispositivo non disponibile verificare sia acceso e '
                  'connesso'))

    def get_flask_sql_call(self, cr, uid, database, context=None):
        """ Prepare a flask call
        """
        verbose = True
        user_pool = self.pool.get('res.users')

        # todo second call (put in first for undo problem?)
        user = user_pool.browse(cr, uid, uid, context=context)
        company = user.company_id

        # Flask agent:
        flask_host = company.flask_host
        flask_port = company.flask_port
        flask_endpoint = company.flask_endpoint

        url = 'http://%s:%s%s' % (flask_host, flask_port, flask_endpoint)
        headers = {
            'content-type': 'application/json',
        }
        payload = {
            'jsonrpc': '2.0',
            'params': {
                # 'command': 'mysql_insert',
                # 'query': query,
                'verbose': True,
                'mysql': {
                    'host': database.ip,
                    'port': database.port,
                    'user': database.username,
                    'password': database.password,
                    'database': database.database,
                    'use_pure': False,
                },
            },
        }
        if flask_endpoint and database.database:
            return url, headers, payload
        else:
            return False  # Not configured for Cabin box Oven

    # Flask JSON function:
    def clean_flask_mysql_job(self, cr, uid, job, context=None):
        """ Clean Cabin Box Oven
        """
        # =====================================================================
        # 1 Call: Robot Oven Box:
        # =====================================================================
        cabin_call = self.get_flask_sql_call(
                cr, uid, job.database_id, context=context)
        if not cabin_call:
            return 'Errore nella chiamata Flask JSON alla macchina di servizio'

        url, headers, payload = cabin_call

        # 1. Delete job ID:
        # todo check if job is in done status?
        job_id = job.id

        query = 'DELETE FROM siord00f WHERE SIORDNUM = %s;' % job_id
        payload['params']['command'] = 'mysql_delete'
        payload['params']['query'] = query

        try:
            response = requests.post(
                url, headers=headers, data=json.dumps(payload))
            response_json = response.json()
            if not response_json['success']:
                raise osv.except_osv(
                    _('Errore chiamata a Cabina:'),
                    _('Errore cancellando il Job in cabina: %s!' %
                      response_json['reply']['error']))
        except:
            raise osv.except_osv(
                _('Errore chiamata a Cabina:'),
                _('Errore cancellando il Job in cabina [%s]!' % url))

        return True

    # OCPUA function:
    def clean_opcua_job(self, cr, uid, source, opcua_ref, context=None):
        """ Remove job to robot
        """
        database_pool = self.pool.get('industria.database')
        production_pool = self.pool.get('industria.production')

        # ---------------------------------------------------------------------
        # Clean on robot:
        # ---------------------------------------------------------------------
        database = source.database_id
        robot = database_pool.get_robot(database)

        # =====================================================================
        # 2 Call: Oven program
        # =====================================================================
        mask = source.opcua_mask

        cleaning_parameter = [
            (0, [
                'FineAnno', 'FineGiorno', 'FineMese',
                'FineMinuto', 'FineOra',

                'InizioAnno', 'InizioGiorno', 'InizioMese',
                'InizioMinuto', 'InizioOra',

                'TempoCambioColore', 'TempoFermo', 'TempoLavoro',

                'Temperatura',
            ]),
            (0.0, [
                # todo 'Velocità'
            ]),
            (False, [
                'Spunta_Completata', 'Spunta_In_Corso',
                # 'Live'
                ]),
            ('', ['Commessa', 'Colore']),
        ]

        # Loop for reset parameter:
        _logger.info('Clean program in robot...')
        for update_value, fields in cleaning_parameter:
            for field in fields:
                try:
                    database_pool.set_data_value(
                        robot, mask % (field, opcua_ref), update_value)
                except:
                    _logger.error('Updating %s field' % field)
                    continue

        # ---------------------------------------------------------------------
        # Reload in ODOO:
        # ---------------------------------------------------------------------
        # todo use original button? need job_id!
        # job_pool.button_load_production_from_robot(
        #    cr, uid, [], context=context)

        production_ids = production_pool.search(cr, uid, [
            ('source_id', '=', source.id),
            ('ref', '=', opcua_ref),
        ], context=context)
        if production_ids:
            production_pool.write(cr, uid, production_ids, {
                # 'source_id': False,
                # 'ref'
                'job_id': False,
                'name': False,
                'temperature': False,
                'speed': False,
                'color': False,
                'start': False,
                'stop': False,
                'duration': False,
                'stop_duration': False,
                'change_duration': False,

                'is_working': False,
                'is_completed': False,
                'is_live': True,
            }, context=context)
            _logger.info('Cleaned program')
        else:
            _logger.error('ODOO production not found!')

        # todo
        # try:
        #     robot.disconnect()
        # except:
        #     _logger.error('Error disconnecting robot OPCUA!\n{}'.format(
        #         sys.exc_info(),
        #     ))

        return True

    def get_data_value(
            self, robot, node_description, comment='', verbose=True):
        """ Extract node data
        """
        node = robot.get_node(node_description)
        try:
            data = node.get_data_value().Value._value
        except:
            print('Cannot read, robot unplugged?')
            return 'ERROR'
        if verbose:
            comment = comment or node_description
            print(comment, data)
        return data

    def set_data_value(self, robot, node_description, value, verbose=True):
        """ Save node data
        """
        from opcua import ua

        try:
            node = robot.get_node(str(node_description))
        except Exception:
            _logger.error('Node name problem: %s' % node_description)
        try:
            node.set_value(
                ua.DataValue(ua.Variant(
                    value,
                    node.get_data_type_as_variant_type()
                )))
            if verbose:
                _logger.info('Update %s with %s' % (
                    node_description, value,
                ))

        except:
            _logger.error('Write parameter %s problem: %s' % (
                node_description, value))
            print('Cannot read, robot unplugged?\n%s' % (sys.exc_info(),))
            return False
        return True

    def update_medium_program_job(self, cr, uid, ids, context=None):
        """ Update medium
        """
        _logger.info('Update medium for program')
        job_pool = self.pool.get('industria.job')
        program_pool = self.pool.get('industria.program')

        job_ids = job_pool.search(cr, uid, [
            ('unused', '=', False),  # Exclude unused marked job
            ('state', '=', 'COMPLETED'),  # Only completed works
            ('database_id.mode', '!=', 'opcua'),  # Exclude OPCUA program
        ], context=context)
        program_medium = {}
        _logger.info('Job for medium %s' % len(job_ids))
        for job in job_pool.browse(cr, uid, job_ids, context=context):
            program = job.program_id
            if program not in program_medium:
                program_medium[program] = [0.0, 0.0]  # q, time
            program_medium[program][0] += job.piece
            program_medium[program][1] += job.job_duration

        program_alarm = {}
        _logger.info('Update medium %s' % len(program_medium))
        for program in program_medium:
            if program_medium[program][0]:
                medium = \
                    program_medium[program][1] / program_medium[program][0]
            else:
                medium = 0.0
            program_pool.write(cr, uid, [program.id], {
                'medium': medium
            }, context=context)
            program_alarm[program] = program.over_alarm

        _logger.info('Unmark medium job error %s' % len(job_ids))
        for job in job_pool.browse(cr, uid, job_ids, context=context):
            program = job.program_id

            alarm = program_alarm.get(program, 0)
            if not alarm:
                alarm = program.medium * 1.5  # If no alarm use 1,5 x medium
            if alarm and job.job_duration > alarm:
                data = {'out_statistic': True}
            else:
                data = {'out_statistic': False}
            job_pool.write(cr, uid, [job.id], data, context=context)
        _logger.info('End update medium for program # job: %s' % len(job_ids))

    def generate_this_picking_from_job(self, cr, uid, ids, context=None):
        """ Generate picking from jobs
        """
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['force_database_id'] = ids[0]
        return self.generate_picking_from_job(cr, uid, ids, context=ctx)

    def generate_picking_from_job(self, cr, uid, ids, context=None):
        """ Generate picking from jobs (all job except fabric job that need
            different management
        """
        if context is None:
            context = {}
        force_database_id = context.get('force_database_id')

        model_pool = self.pool.get('ir.model.data')
        picking_pool = self.pool.get('stock.picking')
        move_pool = self.pool.get('stock.move')
        job_pool = self.pool.get('industria.job')
        company_pool = self.pool.get('res.company')

        company_proxy = company_pool._get_company_browse(
            cr, uid, context=context)

        cl_type = company_proxy.cl_mrp_lavoration_id
        cl_type_id = cl_type.id if cl_type else False
        location_src_id = cl_type.default_location_src_id.id
        location_dest_id = cl_type.default_location_dest_id.id

        domain = [
            ('picking_id', '=', False),
            ('unused', '=', False),

            ('created_at', '!=', False),
            ('ended_at', '!=', False),

            ('state', '=', 'COMPLETED'),

            # ('program_id.product_id', '!=', False),  # With semi product
        ]
        if force_database_id:
            domain.append(('database_id', '=', force_database_id))
        job_ids = job_pool.search(cr, uid, domain, context=context)

        daily_job = {}
        for job in job_pool.browse(cr, uid, job_ids, context=context):
            products = []

            # A1. Normal mono production:
            product = job.force_product_id or job.program_id.product_id
            if product:
                products.append((product, job.piece))

            # A2. Normal mono production (unload):
            # product = job.in_product_id
            # if product:
            #    products.append((product, -job.bar))

            # A3. Fabric half worked:
            for step in job.step_ids:
                program = step.program_id
                for line in step.fabric_ids:  # fabric in job
                    fabric = line.fabric_id
                    flat_total = line.total

                    # Check fabric in program  todo remove?
                    for program_fabric in program.fabric_ids:
                        if fabric == program_fabric.fabric_id:
                            for part in program_fabric.part_ids:
                                product = part.product_id
                                products.append(
                                    (product, flat_total * part.total))

            # B. Multi production:
            for item in job.product_ids:
                products.append((item.product_id, item.piece))

            if not products:
                _logger.error('Jump job, no half worked!')
                continue  # Not used

            # -----------------------------------------------------------------
            # Collect job in daily block:
            # -----------------------------------------------------------------
            database = job.database_id
            origin = '%s [%s]' % (database.name, database.ip)
            if origin not in daily_job:
                daily_job[origin] = {}

            date = '%s 08:00:00' % job.created_at[:10]  # Always at 8 o'clock
            if date not in daily_job[origin]:
                daily_job[origin][date] = {}

            multi_duration = \
                job.duration + job.duration_stop + job.duration_change
            duration = multi_duration or job.job_duration
            linked_job_id = job.id
            for product, piece in products:
                if product not in daily_job[origin][date]:
                    # Total, duration, job:
                    daily_job[origin][date][product] = [0, 0, []]
                daily_job[origin][date][product][0] += piece
                daily_job[origin][date][product][1] += duration
                if linked_job_id:
                    daily_job[origin][date][product][2].append(linked_job_id)

                # Multi product mode clean data:
                duration = 0  # only fist for multi product
                linked_job_id = False

        # Generate picking form collected data:
        new_picking_ids = []
        for origin in daily_job:
            for date in daily_job[origin]:
                # Create picking:
                picking_id = picking_pool.create(cr, uid, {
                    'dep_mode': 'workshop',  # Always
                    'origin': origin,
                    # 'partner_id':
                    'date': date,
                    'min_date': date,
                    'total_work': 0.0,
                    'total_prepare': 0.0,
                    'total_stop': 0.0,
                    'note': '',
                    'state': 'draft',
                    'picking_type_id': cl_type_id,
                    'is_mrp_lavoration': True,
                    # 'location_id': location_id,
                }, context=context)

                new_picking_ids.append(picking_id)
                total_work = 0.0
                for product in daily_job[origin][date]:
                    # Create stock move:
                    qty, duration, job_ids = daily_job[origin][date][product]
                    total_work += duration
                    onchange = move_pool.onchange_product_id(
                        cr, uid, False, product.id, location_src_id,
                        location_dest_id, False)  # no partner
                    move_data = onchange.get('value', {})
                    if qty > 0:
                        move_data.update({
                            'picking_id': picking_id,
                            'product_id': product.id,
                            'product_uom_qty': qty,
                            'location_id': location_src_id,
                            'location_dest_id': location_dest_id,
                            })
                    else:
                        move_data.update({
                            'picking_id': picking_id,
                            'product_id': product.id,
                            'product_uom_qty': qty,
                            'location_id': location_dest_id,
                            'location_dest_id': location_src_id,
                        })

                    move_pool.create(cr, uid, move_data, context=context)

                    # Link job to picking:
                    job_pool.write(cr, uid, job_ids, {
                        'picking_id': picking_id,
                    }, context=context)
                picking_pool.write(cr, uid, [picking_id], {
                    'total_work': total_work / 60.0,
                }, context=context)

        # Return list of picking
        form_view_id = model_pool.get_object_reference(
            cr, uid, 'lavoration_cl_sl', 'view_stock_picking_cl_form'
        )[1]
        tree_view_id = model_pool.get_object_reference(
            cr, uid, 'lavoration_cl_sl', 'view_stock_picking_cl_tree',
        )[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Lavorazioni pendenti da approvare'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            # 'res_id': 1,
            'res_model': 'stock.picking',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', new_picking_ids)],
            'context': {
                'default_dep_mode': 'workshop',
                'open_mrp_lavoration': True,
            },
            'target': 'current',
            'nodestroy': False,
            }

    def generate_fabric_picking_from_job(self, cr, uid, ids, context=None):
        """ Generate picking from jobs Used only for fabric (others use:
            generate_picking_from_job
            force_job_id: all fabric job use this parameter for select job
        """
        if context is None:
            context = {}

        # Context parameters:
        force_job_id = context.get('force_job_id')
        default_dep_mode = context.get('default_dep_mode', 'workshop')

        if not force_job_id:
            # todo is mandatory?
            _logger.error('No job fabric passed (parameter force_job_id)')
            return False
        force_database_id = context.get('force_database_id')

        model_pool = self.pool.get('ir.model.data')
        picking_pool = self.pool.get('stock.picking')
        move_pool = self.pool.get('stock.move')
        quant_pool = self.pool.get('stock.quant')
        job_pool = self.pool.get('industria.job')
        company_pool = self.pool.get('res.company')

        # ---------------------------------------------------------------------
        # Read company parameters:
        # ---------------------------------------------------------------------
        company_proxy = company_pool._get_company_browse(
            cr, uid, context=context)
        # todo hardcoded to remove!!!!!
        #  use: company_proxy.partner_id.id  (not included in TX report)
        # company_partner_id = 29552
        company_partner_id = False

        # CL:
        cl_type = company_proxy.cl_mrp_lavoration_id
        cl_type_id = cl_type.id if cl_type else False
        cl_location_src_id = cl_type.default_location_src_id.id
        cl_location_dest_id = cl_type.default_location_dest_id.id

        # SL:
        sl_type = company_proxy.sl_mrp_lavoration_id
        sl_type_id = sl_type.id if sl_type else False
        sl_location_src_id = sl_type.default_location_src_id.id
        sl_location_dest_id = sl_type.default_location_dest_id.id
        stock_location = sl_type.default_location_src_id.id or False

        # No loop only one job closed:
        daily_job = {}
        job = job_pool.browse(cr, uid, force_job_id, context=context)
        integrate_bom = job.source_id.integrate_bom
        products = []
        # materials = []

        # ---------------------------------------------------------------------
        #                      Fabric and semi product:
        # ---------------------------------------------------------------------
        for step in job.step_ids:
            program = step.program_id
            fabric_length = program.fabric_length / 1000.0  # was mm.
            # todo manage extra semi-product from this program (stenditore)

            for line in step.fabric_ids:  # fabric in job
                fabric = line.fabric_id
                flat_total = line.total * fabric_length  # x length of layer
                # todo manage extra fabric
                # materials.append((fabric, flat_total))  # fabric, mt used
                products.append((fabric, -flat_total))  # fabric, mt used

                # Check fabric in program log XML file  todo remove?
                # -------------------------------------------------------------
                #
                # -------------------------------------------------------------
                for semiproduct in line.product_ids:
                    # todo manage semi-product removed mode?
                    # Load:
                    products.append(
                        (semiproduct.product_id, semiproduct.total))

                    # ---------------------------------------------------------
                    # Append extra BOM elements:
                    # ---------------------------------------------------------
                    if integrate_bom:
                        _logger.info('JOB unload also BOM')
                        for bom_line in semiproduct.product_id.half_bom_ids:
                            component = bom_line.product_id
                            category = component.inventory_category_id.name \
                                       or ''
                            # todo keep as parameter Tessuto:
                            if category.startswith('Tessut'):
                                continue  # Yet used
                            component_qty = -(
                                    semiproduct.total * bom_line.product_qty)
                            products.append(
                                # BOM component, Q. used
                                (component, component_qty))

                # Old management for fabric:
                # for program_fabric in program.fabric_ids:
                #    if fabric == program_fabric.fabric_id:
                #        for part in program_fabric.part_ids:
                #            product = part.product_id
                #            products.append(
                #                (product, flat_total * part.total))

        if not products:  # and not materials:
            _logger.error('No semi-product / raw material found to be loaded!')
            return False

        # ---------------------------------------------------------------------
        #                    Collect job in daily block:
        # ---------------------------------------------------------------------
        if not program:  # todo raise error?
            _logger.error('No program!')

        database = job.database_id
        origin = '%s [PI %s]' % (database.name, program.name)
        if origin not in daily_job:
            daily_job[origin] = {}

        date = '%s 08:00:00' % job.created_at[:10]  # Always at 8 o'clock
        if date not in daily_job[origin]:
            daily_job[origin][date] = {}

        multi_duration = \
            job.duration + job.duration_stop + job.duration_change
        duration = multi_duration or job.job_duration
        fabric_generator_job_id = generator_job_id = job.id
        for product, piece in products:
            if product not in daily_job[origin][date]:
                # Record: Total, duration, job:
                daily_job[origin][date][product] = [0, 0, []]
            daily_job[origin][date][product][0] += piece
            daily_job[origin][date][product][1] += duration
            if fabric_generator_job_id:  # used instead generator for compatib?
                if fabric_generator_job_id not in daily_job[origin][date][
                        product][2]:
                    daily_job[origin][date][product][2].append(
                        fabric_generator_job_id)

            # Multi product mode clean data:
            duration = 0  # only fist for multi product
            generator_job_id = False

        # Generate picking form collected data:
        new_picking_ids = []
        for origin in daily_job:
            for date in daily_job[origin]:
                # Create unload picking (before load!):
                sl_picking_id = picking_pool.create(cr, uid, {
                    'industria_mrp_id': job.industria_mrp_id.id,
                    'dep_mode': default_dep_mode,  # 'workshop',  # Always
                    'origin': origin,
                    'partner_id': company_partner_id,
                    'date': date,
                    'min_date': date,
                    'total_work': 0.0,
                    'total_prepare': 0.0,
                    'total_stop': 0.0,
                    'note': '',
                    'state': 'done',
                    'picking_type_id': sl_type_id,
                    'is_mrp_lavoration': True,
                    # 'location_id': location_id,
                }, context=context)

                # Create load picking:
                cl_picking_id = picking_pool.create(cr, uid, {
                    'industria_mrp_id': job.industria_mrp_id.id,
                    'dep_mode': default_dep_mode,  # 'workshop',  # Always
                    'origin': origin,
                    'partner_id': company_partner_id,
                    'date': date,
                    'min_date': date,
                    'total_work': 0.0,
                    'total_prepare': 0.0,
                    'total_stop': 0.0,
                    'note': '',
                    'state': 'done',
                    'picking_type_id': cl_type_id,
                    'is_mrp_lavoration': True,
                    'linked_sl_id': sl_picking_id,  # Link  document
                    # 'location_id': location_id,
                }, context=context)

                # Link to I40 MRP:
                new_picking_ids.append(cl_picking_id)
                new_picking_ids.append(sl_picking_id)

                total_work = 0.0
                for product in daily_job[origin][date]:
                    # Create stock move:
                    qty, duration, job_ids = daily_job[origin][date][product]
                    total_work += duration
                    if len(job_ids) > 1:
                        _logger.error('More job on this stock move!')
                    if qty > 0:  # CL Document:
                        onchange = move_pool.onchange_product_id(
                            cr, uid, False, product.id, cl_location_src_id,
                            cl_location_dest_id, False)  # no partner
                        move_data = onchange.get('value', {})
                        move_data.update({
                            'picking_id': cl_picking_id,
                            'product_id': product.id,
                            'product_uom_qty': qty,
                            'location_id': cl_location_src_id,
                            'location_dest_id': cl_location_dest_id,
                            'state': 'done',
                            'generator_job_id': job_ids[0] or False,
                        })
                    else:  # SL document:
                        onchange = move_pool.onchange_product_id(
                            cr, uid, False, product.id, sl_location_src_id,
                            sl_location_dest_id, False)  # no partner
                        move_data = onchange.get('value', {})
                        move_data.update({
                            'picking_id': sl_picking_id,
                            'product_id': product.id,
                            # todo used positive Q. in SL:
                            'product_uom_qty': -qty,
                            'location_id': sl_location_dest_id,
                            'location_dest_id': sl_location_src_id,
                            'state': 'done',
                            'generator_job_id': job_ids[0] or False,
                        })
                        # todo integrate with extra data from BOM:

                    # Stock movement:
                    move_pool.create(cr, uid, move_data, context=context)

                    # Unload quants materials:
                    quant_pool.create(cr, uid, {
                        'in_date': date,
                        'cost': 0.0,  # todo
                        'location_id': stock_location,
                        'product_id': product.id,
                        'qty': qty,
                        'lavoration_link_id': cl_picking_id,
                    }, context=context)

                    # Link job to picking:
                    job_pool.write(cr, uid, job_ids, {
                        'picking_id': cl_picking_id,
                        # todo no link for SL?
                    }, context=context)

                # Total work written only in CL:
                picking_pool.write(cr, uid, [cl_picking_id], {
                    'total_work': total_work / 60.0,
                }, context=context)

            """
            # Return list of picking
            form_view_id = model_pool.get_object_reference(
                cr, uid, 'lavoration_cl_sl', 'view_stock_picking_cl_form'
            )[1]
            tree_view_id = model_pool.get_object_reference(
                cr, uid, 'lavoration_cl_sl', 'view_stock_picking_cl_tree',
            )[1]
            # Not used for now:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Lavorazioni pendenti da approvare'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                # 'res_id': 1,
                'res_model': 'stock.picking',
                'view_id': tree_view_id,
                'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
                'domain': [('id', 'in', new_picking_ids)],
                'context': {
                    'default_dep_mode': 'workshop',
                    'open_mrp_lavoration': True,
                },
                'target': 'current',
                'nodestroy': False,
                }"""
            return True

    def mssql_connect(self, cr, uid, ids, context=None):
        """ Connection with database return cursor
        """
        database = self.browse(cr, uid, ids, context=context)[0]
        as_dict = True

        try:
            if database.mode == 'mssql':
                try:
                    import pymssql
                except:
                    _logger.error('Error no module pymssql installed!')
                    return False

                connection = pymssql.connect(
                    host=r'%s:%s' % (database.ip, database.port),
                    user=database.username,
                    password=database.password,
                    database=database.database,
                    as_dict=as_dict)

            elif database.mode == 'mysql':
                try:
                    import MySQLdb, MySQLdb.cursors
                except:
                    _logger.error('Error no module MySQLdb installed!')
                    return False

                connection = MySQLdb.connect(
                    host=database.ip,
                    user=database.username,
                    passwd=database.password,
                    db=database.database,
                    cursorclass=MySQLdb.cursors.DictCursor,
                    charset='utf8',
                    )
            else:
                return False
        except:
            return False
        return connection  # .cursor()

    # -------------------------------------------------------------------------
    # Button event:
    # -------------------------------------------------------------------------
    def test_database_connection(self, cr, uid, ids, context=None):
        """ Test database connection
        """
        cursor = self.mssql_connect(cr, uid, ids, context=context)
        if cursor:
            raise osv.except_osv(
                _('Connection test:'),
                _('OpenERP successfully connected with SQL database using '
                  'this parameters!'))
        else:
            raise osv.except_osv(
                _('Connection error:'),
                _('OpenERP cannot connect with SQL database using this '
                  'parameters!'))

    def import_program(self, cr, uid, ids, context=None):
        """ Update program list
        """
        program_pool = self.pool.get('industria.program')

        database_id = ids[0]
        connection = self.mssql_connect(cr, uid, ids, context=context)
        if not connection:
            _logger.error('MySQL Robot not present, Mini PC not available!')
            return False
        cursor = connection.cursor()

        try:
            query = """
                SELECT *
                FROM programs;
                """
            cursor.execute(query)
        except:
            raise osv.except_osv(
                _('Error SQL access'),
                'Executing query %s: \n%s' % (
                    query,
                    sys.exc_info(),
                ))

        for record in cursor:
            industria_ref = record['id']
            data = {
                'database_id': database_id,
                'industria_ref': industria_ref,

                'code': record['name'],
                'name': record['description'],
                'piece': record['npieces'],
                'timeout': record['maxexecutiontime'],
                # TODO created_at | updated_at
            }

            program_ids = program_pool.search(cr, uid, [
                ('database_id', '=', database_id),
                ('industria_ref', '=', industria_ref),
            ], context=context)
            if program_ids:
                program_pool.write(
                    cr, uid, program_ids, data, context=context)
            else:
                program_pool.create(
                    cr, uid, data, context=context)
        return True

    def import_robot(self, cr, uid, ids, context=None):
        """ Update robot list
        """
        robot_pool = self.pool.get('industria.robot')

        database_id = ids[0]
        connection = self.mssql_connect(cr, uid, ids, context=context)
        if not connection:
            _logger.error('MySQL Robot not present, Mini PC not available!')
            return False

        cursor = connection.cursor()

        try:
            query = """
                SELECT *
                FROM sources
                """
            cursor.execute(query)
        except:
            raise osv.except_osv(
                _('Error SQL access'),
                'Executing query %s: \n%s' % (
                    query,
                    sys.exc_info(),
                ))

        for record in cursor:
            industria_ref = record['id']
            data = {
                'database_id': database_id,
                'industria_ref': industria_ref,

                'ip': record['ip'],
                'name': record['description'] or record['name'],
            }

            source_ids = robot_pool.search(cr, uid, [
                ('database_id', '=', database_id),
                ('industria_ref', '=', industria_ref),
            ], context=context)

            if source_ids:
                robot_pool.write(
                    cr, uid, source_ids, data, context=context)
            else:
                robot_pool.create(cr, uid, data, context=context)
        return True

    def import_job(self, cr, uid, ids, context=None):
        """ Update job list
        """
        def sql_get_date(ts):
            """ Generate date for database
            """
            if not ts:
                return False

            # Bug: if refresh old value may be theres GMT or not so error!
            dls_hours = 1  # 2  # TODO change!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
            dls_dt = relativedelta(hours=dls_hours)
            # extra_gmt = datetime.now() - datetime.utcnow()
            return (ts - dls_dt).strftime(
                DEFAULT_SERVER_DATETIME_FORMAT)

        # ---------------------------------------------------------------------
        # Import mode:
        # ---------------------------------------------------------------------
        # 1. FTP:
        database_proxy = self.browse(cr, uid, ids, context=context)[0]
        if database_proxy.mode == 'ftp':
            return self.import_job_ftp(cr, uid, ids, context=context)

        # 2. OPCUA:
        if database_proxy.mode == 'opcua':
            return True  # TODO not used for now!

        # 2. MY SQL:
        _logger.info('Import Job via M*SQL')
        # todo create context from ID (partial run)
        job_pool = self.pool.get('industria.job')
        robot_pool = self.pool.get('industria.robot')
        program_pool = self.pool.get('industria.program')
        database_id = ids[0]

        # Start from last imported:
        try:
            cr.execute('''
                SELECT max(industria_ref) 
                FROM industria_job 
                WHERE database_id = %s''' % database_id)
            records = cr.fetchall()
            from_industria_ref = records[0][0] or 0
        except:
            from_industria_ref = False
        _logger.warning('Load SQL record from ID >= %s' % from_industria_ref)

        connection = self.mssql_connect(cr, uid, ids, context=context)
        cursor = connection.cursor()

        previous_id = False
        try:
            if from_industria_ref:
                query = "SELECT * FROM jobs WHERE id >= %s;" % \
                        from_industria_ref

                # Find last record to create join element:
                last_ids = job_pool.search(cr, uid, [
                    ('industria_ref', '=', from_industria_ref),
                ], context=context)
                if last_ids:
                    previous_id = last_ids[0]
            else:
                query = "SELECT * FROM jobs;"
            cursor.execute(query)
        except:
            raise osv.except_osv(
                _('Error SQL access'),
                'Executing query %s: \n%s' % (
                    query,
                    sys.exc_info(),
                ))
        # partner_id = database.partner_id.id

        # Load program:
        program_db = {}
        program_ids = program_pool.search(cr, uid, [
            ('database_id', '=', database_id),
        ], context=context)
        for program in program_pool.browse(
                cr, uid, program_ids, context=context):
            program_db[program.industria_ref] = program

        # Load robot:
        robot_db = {}
        source_ids = robot_pool.search(cr, uid, [
            ('database_id', '=', database_id),
        ], context=context)
        for robot in robot_pool.browse(cr, uid, source_ids, context=context):
            robot_db[robot.industria_ref] = robot.id

        # Update program for robot:
        update_program = []
        counter = 0
        for record in cursor:
            counter += 1
            if not counter % 50:
                _logger.info('Job imported %s' % counter)
            industria_ref = record['id']
            program = program_db.get(record['program_id'], False)
            program_id = program.id
            piece = program.piece or 1
            source_id = robot_db.get(record['source_id'], False)
            if source_id and program_id not in update_program:
                update_program.append(program_id)

                # Assign robot to the program (every program own to the robot)
                program_pool.write(cr, uid, [program_id], {
                    'source_id': source_id,
                }, context=context)

            data = {
                'previous_id': previous_id,
                'industria_ref': industria_ref,

                # TODO check correct format
                'created_at': sql_get_date(record['created_at']),
                'updated_at': sql_get_date(record['updated_at']),
                'ended_at': sql_get_date(record['ended_at']),

                'source_id': source_id,
                'program_id': program_id,
                'database_id': database_id,
                'state': record['state'],
                'piece': piece,
            }

            job_ids = job_pool.search(cr, uid, [
                ('database_id', '=', database_id),
                ('industria_ref', '=', industria_ref),
            ], context=context)
            if job_ids:
                job_pool.write(
                    cr, uid, job_ids, data, context=context)
                previous_id = job_ids[0]
            else:
                previous_id = job_pool.create(
                    cr, uid, data, context=context)

        # Update medium:
        self.update_medium_program_job(cr, uid, ids, context=context)
        return True

    def import_job_ftp(self, cr, uid, ids, context=None):
        """ Import Job from FTP folder
        """
        def get_date(date):
            """ Extract FTP date
            """
            daylight = -1  # Manage better
            date = date.strip()
            try:
                date_part = date.split('-')
                year_part = date_part[:3]
                hour_part = date_part[3].split(':')

                date = '%04d-%02d-%02d %02d:%02d:%02d' % (
                    int(year_part[2]),
                    int(year_part[1]),
                    int(year_part[0]),

                    int(hour_part[0]) + daylight,
                    int(hour_part[1]),
                    int(hour_part[2]),
                )
            except:
                _logger.error('Cannot convert in date: %s' % date)
                date = False
            return date

        _logger.info('Import Job via FTP')
        job_pool = self.pool.get('industria.job')
        robot_pool = self.pool.get('industria.robot')
        program_pool = self.pool.get('industria.program')
        database_id = ids[0]
        database = self.browse(cr, uid, database_id, context=context)
        partner_id = database.partner_id.id

        # ---------------------------------------------------------------------
        # File operation:
        # ---------------------------------------------------------------------
        command = database.ftp_command
        fullname = os.path.expanduser(database.ftp_fullname)
        root_path = os.path.dirname(fullname)
        history_path = os.path.join(root_path, 'history')
        os.system('mkdir -p %s' % history_path)
        history_fullname = os.path.join(
            history_path,
            str(datetime.now()).replace(':', '_').replace('/', '-'),
        )

        if not os.path.isfile(fullname):
            # Extract FTP file from Robot:
            os.system(command)  # Get file and clean on server

        if not os.path.isfile(fullname):
            _logger.error(
                'Cannot extract file form robot via FTP: %s' % fullname)
            return False

        # ---------------------------------------------------------------------
        # Import operation:
        # ---------------------------------------------------------------------
        # Load robot:
        robot_ids = robot_pool.search(cr, uid, [
            ('database_id', '=', database_id),
        ], context=context)
        if not robot_ids:
            _logger.error('Not found robot for this database!')
            return False
        robot_id = robot_ids[0]

        # Load program:
        program_ids = program_pool.search(cr, uid, [
            ('database_id', '=', database_id),
        ], context=context)
        program_db = {}
        for program in program_pool.browse(
                cr, uid, program_ids, context=context):
            program_db[program.name] = program.id

        # Load Jobs:
        counter = 0
        for line in open(fullname, 'r'):
            counter += 1
            row = line.strip().split(';')
            if not line:
                continue

            if len(row) != 5:
                _logger.error('%s Wrong number of columns: %s' % (
                    counter, line))
                continue

            program_name = row[0].replace('\x00', '')
            # program_ref = row[1]
            # program_code = row[2]
            from_date = get_date(row[3])
            to_date = get_date(row[4])

            # Check mandatory parameters:
            if not all((from_date, to_date, program_name)):
                _logger.error('Missed data: %s' % line)
                continue

            if program_name in program_db:
                program_id = program_db[program_name]
            else:
                program_id = program_pool.create(cr, uid, {
                    'name': program_name,
                    'partner_id': partner_id,
                    'source_id': robot_id,
                    'database_id': database_id,
                }, context=context)
                program_db[program_name] = program_id

            job_ids = job_pool.search(cr, uid, [
                ('created_at', '=', from_date),
            ], context=context)

            data = {
                'created_at': from_date,
                'ended_at': to_date,
                'database_id': database_id,
                'program_id': program_id,
                'partner_id': partner_id,
                'state': 'COMPLETED',
                'source_id': robot_id,
                'piece': 1,  # one job one piece always
            }
            if job_ids:
                job_pool.write(cr, uid, job_ids, data, context=context)
            else:
                job_pool.create(cr, uid, data, context=context)

        # Update medium
        self.update_medium_program_job(cr, uid, ids, context=context)

        _logger.info('Read file, moved in %s' % history_fullname)
        shutil.move(fullname, history_fullname)
        return True

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'partner_id': fields.many2one(
            'res.partner', 'Supplier'),

        'opcua_ip': fields.char('OPCUA: Server', size=15),
        'opcua_port': fields.integer('OPCUA: Posta'),

        'ip': fields.char('IP address', size=15),
        'username': fields.char('Username', size=64),
        'password': fields.char('Password', size=64),
        'database': fields.char('Database', size=64),
        'port': fields.integer('Port'),
        'last_stat_id': fields.integer(
            'Ultimo ID',
            help='Ultimo ID dati statitici recuperati dal database,'
                 'utilizzato per evitare di leggere sempre tutte le'
                 'righe presenti.'),
        'note': fields.text('Note'),
        'ftp_command': fields.text(
            'FTP command', help='FTP command for unload Job'),
        'ftp_fullname': fields.char(
            'FTP fullname', size=180, help='Fullname for file with log'),
        'mode': fields.selection([
            ('mysql', 'My SQL'),
            ('mssql', 'MS SQL'),
            ('ftp', 'FTP'),
            ('opcua', 'OPCUA'),
            ('file', 'File'),
        ], 'Mode', required=True),
    }

    _defaults = {
        'mode': lambda *x: 'mysql',
        'port': lambda *a: 3306,
    }


class IndustriaRobot(orm.Model):
    """ Model name: Industria Robot
    """

    _name = 'industria.robot'
    _description = 'Robot'
    _rec_name = 'name'
    _order = 'name'

    '''
    def button_generate_matching_product_program_all(
            self, cr, uid, ids, context=None):
        """ Update all program - product
        """
        program_pool = self.pool.get('industria.program')
        robot_id = ids[0]
        program_ids = program_pool.search(cr, uid, [
            ('source_id', '=', robot_id),
        ], context=context)

        counter = 0
        total = len(program_ids)
        for program_id in program_ids:
            counter += 1
            # Call button action:
            _logger.info('Updating program %s of %s' % (counter, total))
            program_pool.button_generate_matching_product_program(
                cr, uid, [program_id], context=context)'''

    def get_opcua_record(self, robot, source, ref):
        """ Extract OPCUA record from robot
        """
        database_pool = self.pool.get('industria.database')
        variables = [
            'Colore', 'Commessa',
            'Temperatura', 'Velocità',

            'FineAnno', 'FineGiorno', 'FineMese',
            'FineMinuto', 'FineOra',
            'InizioAnno', 'InizioGiorno', 'InizioMese',
            'InizioMinuto', 'InizioOra',

            'Spunta_Completata', 'Spunta_In_Corso',

            'TempoCambioColore', 'TempoFermo', 'TempoLavoro',
            'Live',
        ]
        mask = str(source.opcua_mask)
        print('\nCommessa %s' % ref)
        record = {}
        for variable in variables:
            record[variable] = database_pool.get_data_value(
                robot,
                mask % (str(variable), ref),
                verbose=False,
            )
        return record

    def write_record_in_odoo(
            self, cr, uid, robot_id, record, ref, context=None):
        """ Write record in ODOO
        """
        if context is None:
            context = {}
        force_job_id = context.get('force_job_id')

        production_pool = self.pool.get('industria.production')
        database_pool = self.pool.get('industria.database')

        data = {
            # 'source_id': robot_id,
            'ref': ref,
            'name': record.get('Commessa'),
            'color': record.get('Colore'),
            'temperature': record.get('Temperatura'),
            'speed': record.get('Velocità'),
            'start': database_pool.extract_date(record, mode='Inizio'),
            'stop': database_pool.extract_date(record, mode='Fine'),

            'duration': record.get('TempoLavoro'),
            'stop_duration': record.get('TempoFermo'),
            'change_duration': record.get('TempoCambioColore'),

            'is_working': database_pool.extract_boolean(
                record.get('Spunta_In_Corso')),
            'is_completed': database_pool.extract_boolean(
                record.get('Spunta_Completata')),
            'is_live': database_pool.extract_boolean(
                record.get('Live')),
        }
        if robot_id:
            data['source_id'] = robot_id

        if force_job_id:
            data['job_id'] = force_job_id

        # Check in ODOOs:
        production_ids = production_pool.search(cr, uid, [
            ('ref', '=', ref),
            ('source_id', '=', robot_id),
        ], context=context)
        if production_ids:
            production_pool.write(
                cr, uid, production_ids, data, context=context)
        else:
            production_pool.create(
                cr, uid, data, context=context)
        return True

    def button_load_production_from_robot(self, cr, uid, ids, context=None):
        """ Load from robot list of production
        """
        if context is None:
            context = {}
        reload_only_ref = context.get('reload_only_ref')
        if reload_only_ref:
            check_range = [reload_only_ref]
        else:
            check_range = range(21)

        database_pool = self.pool.get('industria.database')

        robot_id = ids[0]
        source = self.browse(cr, uid, robot_id, context=context)
        if source.database_id.mode != 'opcua':
            raise osv.except_osv(
                _('Import non permesso'),
                _('Il robot non permette la importazione delle commesse'),
            )

        robot = database_pool.get_robot(source.database_id)
        for ref in check_range:
            # Extract from robot:
            record = self.get_opcua_record(robot, source, ref)

            # Write in ODOO:
            self.write_record_in_odoo(
                cr, uid, robot_id, record, ref, context=context)

        try:
            robot.disconnect()
        except:
            pass
        return True

    def get_today_state(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate (ensure one)
        """
        item_id = ids[0]
        res = {}
        css = u"""
            @chart-height:300px;
            @grid-color:#aaa;
            @bar-color:#F16335;
            @bar-thickness:50px;
            @bar-rounded: 3px;
            @bar-spacing:30px;
            .chart-wrap{
                margin-left:50px;
                font-family:sans-serif;
                .title{
                    font-weight:bold;
                    font-size:1.62em;
                    padding:0.5em 0 1.8em 0;
                    text-align:center;
                    white-space:nowrap;
                  }
                &.vertical .grid{
                transform:translateY(@chart-height/2 - @chart-width/2)
                translateX(@chart-width/2 - @chart-height/2) rotate(-90deg);

                .bar::after{
                    transform: translateY(-50%) rotate(45deg);
                    display: block;
                    }
                &::before,&::after{
                    transform:translateX(-0.2em) rotate(90deg);
                    }
                }

            height:@chart-width;
            width:@chart-height;
            .grid{
                position:relative;
                padding:5px 0 5px 0;
                height:100%;
                width:100%;
                border-left:2px solid @grid-color;
                background:repeating-linear-gradient(
                    90deg,transparent,transparent 19.5%,
                    fadeout(@grid-color,30%) 20%);
                &::before{
                    font-size:0.8em;
                    font-weight:bold;
                    content:'0%';
                    position:absolute;
                    left:-0.5em;
                    top:-1.5em;
                    }
                &::after{
                    font-size:0.8em;
                    font-weight:bold;
                    content:'100%';
                    position:absolute;
                    right:-1.5em;
                    top:-1.5em;
                    }
                }

            .bar {
                width: var(--bar-value);
                height:@bar-thickness;
                margin:@bar-spacing 0;
                background-color:@bar-color;
                border-radius:0 @bar-rounded @bar-rounded 0;
                &:hover{opacity:0.7; }
                &::after{
                    content:attr(data-name);
                    margin-left:100%;
                    // line-height:@bar-thickness;
                    padding:10px;
                    display:inline-block;
                    white-space:nowrap;
                    }
                }
            }
        """

        html = u"<style>%s</style>" % css
        html += u"""
            <h1>Bar Chart HTML</h1>
            <div class="chart-wrap vertical">
                <h2 class="title">Bar Chart HTML Example: HTML And CSS</h2>

                <div class="grid">
                    <div class="bar" style="--bar-value:85%;"
                        data-name="Your Blog" title="Your Blog 85%"></div>
                    <div class="bar" style="--bar-value:23%;"
                        data-name="Medium" title="Medium 23%"></div>
                    <div class="bar" style="--bar-value:7%;"
                        data-name="Tumblr" title="Tumblr 7%"></div>
                    <div class="bar" style="--bar-value:38%;"
                        data-name="Facebook" title="Facebook 38%"></div>
                    <div class="bar" style="--bar-value:35%;"
                        data-name="YouTube" title="YouTube 35%"></div>
                    <div class="bar" style="--bar-value:30%;"
                        data-name="LinkedIn" title="LinkedIn 30%"></div>
                    <div class="bar" style="--bar-value:5%;"
                        data-name="Twitter" title="Twitter 5%"></div>
                    <div class="bar" style="--bar-value:20%;"
                        data-name="Other" title="Other 20%"></div>
              </div>
            </div>
        """

        res[item_id] = html
        return res

    _columns = {
        'ip': fields.char('IP address', size=15),
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Codice', size=20, required=True),
        'site_code': fields.char(
            'Codice impianto', size=20,
            help='Codice usato spesso per indetificare '
                 'l\'impianto'),
        'ref_code': fields.char('Riferimento impianto', size=20),
        'opcua_mask': fields.char('OPCUA Mask', size=180),
        'industria_ref': fields.integer('Industria ref key'),
        'database_id': fields.many2one(
            'industria.database', 'Database'),
        'partner_id': fields.related(
            'database_id', 'partner_id',
            type='many2one', relation='res.partner',
            string='Supplier', store=True),
        'note': fields.text('Note'),

        # Fabric custom:
        'fabric_tender_name': fields.char('Nome stenditore'),
        'fabric_prefix_cad': fields.char('Prefisso disegni CAD (Robot)'),
        'fabric_cad_path': fields.char('ISO path (ODOO)'),
        'fabric_tender_path': fields.char('Stenditore path'),
        'max_length': fields.integer(
            'Massima lunghezza (mm.)',
            help='Massima lunghezza del piano di posa tessuto in mm. '
                 '(per valutare il massimo numero di gradini)!'),
        'max_layer': fields.integer(
            'Massimo numero strati',
            help='Totale teorico degli strati di questo programma, notare che'
                 'potrebbero dipendere anche dal tipo di tessuto scelto!'),
        'max_gap': fields.integer(
            'Massimo gap',
            help='Massimo numero di gap che possono esserci tra un gradino'
                 'e l\'altro'),
        'integrate_bom': fields.boolean(
            'Integra DB',
            help='Indica che lo scarico tessuti deve essere integrato anche'
                 'con i componenti della distinta base (esclusi i tessuti'
                 'già conteggiati)'),
        'today_state': fields.function(
            get_today_state, 'Status', type='text', method=True),
    }

    _defaults = {
        'max_layer': lambda *x: 30,
    }


class IndustriaProgram(orm.Model):
    """ Model name: Industria Program
    """

    _name = 'industria.program'
    _description = 'Programs'
    _rec_name = 'name'
    _order = 'name'

    def get_selected_product(self, cr, uid, mask, context=None):
        """ Utility for get selected product
        """
        query = 'SELECT id FROM product_product ' \
                'WHERE default_code ilike \'%s\';' % mask
        cr.execute(query)
        return [item[0] for item in cr.fetchall()]

    def button_generate_matching_product_program(
            self, cr, uid, ids, context=None):
        """ Show list of product
        """
        part_pool = self.pool.get('industria.program.fabric.part')
        product_pool = self.pool.get('product.product')

        _logger.info('Clean all matching')
        cr.execute('DELETE FROM product_industria_part_rel;')

        _logger.info('Collect data (only active)')
        part_ids = part_pool.search(cr, uid, [
            ('fabric_id.program_id.active', '=', True),
            ], context=context)

        collect_data = {}
        for part in part_pool.browse(cr, uid, part_ids, context=context):
            mask = part.mask
            if not mask:
                _logger.error('Mask not found, jumped')
                continue
            for product_id in self.get_selected_product(  # mask query
                    cr, uid, part.mask, context=context):
                if product_id in collect_data:
                    collect_data[product_id].append(part.id)
                else:
                    collect_data[product_id] = [part.id]
        _logger.info('Create new matching')
        for product_id in collect_data:
            product_pool.write(cr, uid, [product_id], {
                'industria_rule_ids': [(6, 0, collect_data[product_id])],
            }, context=context)
        return True

    def update_all_job_piece(self, cr, uid, ids, context=None):
        """ Force piece as in program on all jobs
        """
        program_id = ids[0]
        program = self.browse(cr, uid, program_id, context=context)
        job_pool = self.pool.get('industria.job')
        job_ids = job_pool.search(cr, uid, [
            ('program_id', '=', program_id),
        ], context=context)

        return job_pool.write(cr, uid, job_ids, {
            'piece': program.piece,
        }, context=context)

    _columns = {
        'active': fields.boolean('Attivo'),
        'code': fields.char('Code', size=40),
        'name': fields.char('Name', size=64, required=True),
        'industria_ref': fields.integer('Industria ref key'),
        'timeout': fields.integer('Timeout'),
        'piece': fields.integer('Total piece x job'),
        'source_id': fields.many2one(
            'industria.robot', 'Robot'),
        'database_id': fields.many2one(
            'industria.database', 'Database'),
        'product_id': fields.many2one(
            'product.product', 'Semi product'),
        'in_product_id': fields.many2one(  # Not used for now
            'product.product', 'Matariale input'),
        'partner_id': fields.related(
            'source_id', 'partner_id',
            type='many2one', relation='res.partner',
            string='Supplier', store=True),

        # Fabric:
        'fabric_length': fields.float(
            'Lunghezza tessuto mm.', digits=(10, 2),
            help='Utilizzato come default per gli strati di tessuto'),
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
        'fabric_gap': fields.char(
            'Elenco gap sagome', size=180,
            help='Utilizzato per il calcolo dei gradino, è la lista dei '
                 'salti tra una saboma e l\'altra, es per uno schema con 4'
                 'sagome di larghezza 500mm: 500|1000|1500|2000'),
        'fabric_filename': fields.char('Nome file ISO', size=60),

        'mode': fields.related(
            'database_id', 'mode', type='selection', string='Mode',
            selection=[
                ('mysql', 'My SQL'),
                ('mssql', 'MS SQL'),
                ('ftp', 'FTP'),
                ('opcua', 'OPCUA'),
                ('file', 'File'),
            ], readonly=True),
        'note': fields.text('Note'),
        'medium': fields.float(
            'Media',
            help='Media calcolata giornalmente sui lavori di questo '
                 'programma'),
        'over_alarm': fields.float(
            'Allarme', help='Tempo per considerare il programma fuori media'),
    }

    _defaults = {
        'active': lambda *x: True,
        'piece': lambda *x: 1,
        'max_layer': lambda *x: 30,
    }


class IndustriaProgramFabric(orm.Model):
    """ Model name: Industria Program fabric
    """

    _name = 'industria.program.fabric'
    _description = 'Programma tessuti'
    _rec_name = 'fabric_id'
    # _order = 'fabric_id'

    _columns = {
        'program_id': fields.many2one(
            'industria.program', 'Programma'),
        'fabric_id': fields.many2one(
            'product.product', 'Tessuto'),
        'total': fields.float('Pezzi'),
    }


class IndustriaProgramFabricPart(orm.Model):
    """ Model name: Industria Program fabric
    """

    _name = 'industria.program.fabric.part'
    _description = 'Programma parti tessuti'
    _rec_name = 'product_id'
    _order = 'total desc'

    def name_get(self, cr, uid, ids, context=None):
        """ Override for return correct name
        """
        res = []
        for part in self.browse(cr, uid, ids, context=context):
            fabric = part.fabric_id
            parts = len(fabric.part_ids)
            res.append((part.id, '%s: %s [pz %s]%s' % (
                fabric.program_id.code,
                part.mask,
                int(part.total),
                '' if parts <= 1 else ' (parti %s)' % parts,
            )))
        return res

    def button_show_selection(self, cr, uid, ids, context=None):
        """ Show list of product
        """
        program_pool = self.pool.get('industria.program')
        # todo
        current = self.browse(cr, uid, ids, context=context)[0]
        mask = current.mask
        product_ids = program_pool.get_selected_product(
            cr, uid, mask, context=context)

        model_pool = self.pool.get('ir.model.data')
        view_id = False
        # model_pool.get_object_reference('module_name', 'view_name')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Prodotti toccati'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            # 'res_id': 1,
            'res_model': 'product.product',
            'view_id': view_id,  # False
            'views': [(view_id, 'tree'), (False, 'form')],
            'domain': [('id', 'in', product_ids)],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    _columns = {
        'fabric_id': fields.many2one(
            'industria.program.fabric', 'Tessuto', ondelete='cascade'),
        'product_id': fields.many2one('product.product', 'Semilavorato'),
        'program_id': fields.related(
            'fabric_id', 'program_id',
            type='many2one', relation='industria.program',
            string='Programma', store=True),
        'fabric_length': fields.related(
            'program_id', 'fabric_length',
            type='float', string='Lunghezza tessuto mm.', digits=(10, 2),
            ),
        'mask': fields.char(
            'Maschera', size=20, required=True,
            help='Maschera prodotto che possono essere creati con questa dima'
                 ', es.: TS_29TX%'),
        'total': fields.float('Pezzi'),
    }


class IndustriaProgramParameterOpcua(orm.Model):
    """ Model name: Industria Program Parameter OPCUA
    """

    _name = 'industria.program.parameter.opcua'
    _description = 'Programs parameter opcua'
    _rec_name = 'name'
    _order = 'name'

    _columns = {
        'name': fields.char(
            'Name', size=64, required=True),
        'opcua_variable': fields.char(
            'OPCUA Variabile', size=80, required=True),
        'type': fields.selection([
            ('float', 'Reale'),
            ('integer', 'Intero'),
            ('char', 'Stringa'),
            ], 'Tipo dato', required=True)
        }

    _defaults = {
        'type': lambda *x: 'char',
    }


class IndustriaJobProduct(orm.Model):
    """ Model name: Industria Program Product
    """

    _name = 'industria.job.product'
    _description = 'Job program'
    _rec_name = 'product_id'
    _order = 'sequence, product_id'

    _columns = {
        'sequence': fields.integer('Seq.'),
        'job_id': fields.many2one('industria.job', 'Job', ondelete='cascade'),
        # 'source_id': fields.related(
        #    'job_id', 'source_id', type='many2one',
        #    relation='industria.robot',
        #    string='robot_id'),
        'product_id': fields.many2one(
            'product.product', 'Prodotto', required=True),
        'piece': fields.integer('Pezzi', required=True),
    }


class IndustriaProgramParameter(orm.Model):
    """ Model name: Industria Program Parameter
    """

    _name = 'industria.program.parameter'
    _description = 'Programs parameter'
    _rec_name = 'opcua_id'
    _order = 'opcua_id'

    _columns = {
        'opcua_id': fields.many2one(
            'industria.program.parameter.opcua', 'OPCUA Param.',
            required=True),
        'program_id': fields.many2one(
            'industria.program', 'Programma'),
        'value': fields.char(
            'Valore', size=20, required=True),
    }


class IndustriaJob(orm.Model):
    """ Model name: Industria Job
        Field name keep as in MySQL for fast import
    """

    _name = 'industria.job'
    _description = 'Jobs'
    _rec_name = 'created_at'
    _order = 'created_at desc'

    def get_make_filename(self, job):
        """ Extract make filename
        """
        robot = job.source_id
        tender_path = robot.fabric_tender_path
        fullname = os.path.expanduser(
            os.path.join(tender_path, 'job_%s.txt' % job.id))
        return fullname

    def open_job_picking(self, cr, uid, ids, context=None):
        """ Open picking job
        """
        # todo raise error!
        job = self.browse(cr, uid, ids, context=context)[0]
        picking_id = job.picking_id.id
        if not picking_id:
            raise osv.except_osv(
                _('Errore'),
                _('Picking non presente!'),
                )

        # model_pool = self.pool.get('ir.model.data')
        # view_id = model_pool.get_object_reference(
        #     cr, uid, 'module_name', 'view_name')[1]
        view_id = False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Picking'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': picking_id,
            'res_model': 'stock.picking',
            'view_id': view_id,
            'views': [(False, 'form')],
            'domain': [],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    def send_fabric_job(self, cr, uid, ids, context=None):
        """ Send job to tender
        """
        def get_date(date):
            """ Extract FTP date
            """
            date = date.strip()[:10]
            if not date:
                return ''
            return '%s/%s/%s' % (
                date[8:],
                date[5:7],
                date[:4],
            )

        i40_pool = self.pool.get('industria.mrp')

        job_id = ids[0]
        job = self.browse(cr, uid, job_id, context=context)
        industria_mrp_id = job.industria_mrp_id.id
        robot = job.industria_mrp_id.robot_id
        color_order = {}
        pos = 0
        for color in robot.color_ids:
            pos += 1
            color_order[color.code] = pos  # todo use forced color.name?

        date = get_date(job.created_at)
        from_mm = 0
        gap = 0
        file_text = '$D$|%s|$O$|Job_%s' % (date, job_id)

        robot = job.source_id
        tender_name = robot.fabric_tender_name
        fullname = self.get_make_filename(job)
        file_out = open(fullname, 'w')

        data_files = []
        data_fabric = {}
        counter = 0

        file_text += '|$S$'

        # Step loop for fabric:
        step_pos = {}
        pos = 0
        for step in job.step_ids:
            step_pos[step] = pos
            pos += 1

        for step in job.step_ids:
            counter += 1
            program = step.program_id
            prefix_tender_file = robot.fabric_prefix_cad
            length = int(program.fabric_length)
            iso_filename = program.fabric_filename
            iso_fullname = '%s\\%s' % (prefix_tender_file, iso_filename)
            to_mm = int(from_mm + length + gap)

            file_text += '|GR%s:%s;%s' % (counter, from_mm, to_mm)
            from_mm = to_mm

            # Block files:
            data_files.append(iso_fullname)

            # Block fabric:
            for fabric in step.fabric_ids:
                fabric_product = fabric.fabric_id
                if fabric_product not in data_fabric:
                    data_fabric[fabric_product] = [
                        '%s|%s|%s' % (
                            fabric_product.default_code,
                            fabric_product.name,
                            ' ',  # Bagni
                        ),
                        [0 for element in step_pos],  # Q block (total)
                    ]

                total = fabric.total
                data_fabric[fabric_product][1][step_pos[step]] += total

        # ISO file:
        file_text += '|$M$'
        for iso_fullname in data_files:
            file_text += '|%s' % iso_fullname

        file_text += '|$CS$|%s' % tender_name

        # ---------------------------------------------------------------------
        # Write file:
        # ---------------------------------------------------------------------
        # Setup order with fabric color:
        data_fabric_sort = sorted(
            data_fabric,
            key=lambda f: color_order.get(
                i40_pool.extract_fabric_part(f.default_code or '')[2],
                0))
        # Loop for materasso:
        for fabric_product in data_fabric_sort:
            fabric_text, totals = data_fabric[fabric_product]
            file_text += '|$C$|%s' % fabric_text
            file_text += '|$Q$'
            for item in totals:
                file_text += '|%s' % item
        file_text += '|\n'

        file_out.write(file_text)
        file_out.close()

        # ---------------------------------------------------------------------
        # Log message:
        # ---------------------------------------------------------------------
        if industria_mrp_id:
            i40_pool.write_log_chatter_message(
                cr, uid, [industria_mrp_id],
                '[JOB] Job inviato a cartella MAKE, file: %s' % fullname
                , context=context)
        else:
            _logger.error('Job not linked in I40 Order: %s' % fullname)

        self.write(cr, uid, ids, {
            'state': 'RUNNING',
        }, context=context)

    def restart_fabric_job(self, cr, uid, ids, context=None):
        """ Send job to tender
        """
        i40_pool = self.pool.get('industria.mrp')

        industria_mrp_id = False
        fullname = 'NON TROVATO'
        try:
            # Delete file if present:
            job = self.browse(cr, uid, ids, context=context)[0]
            industria_mrp_id = job.industria_mrp_id.id

            fullname = self.get_make_filename(job)
            if os.path.isfile(fullname):
                _logger.warning('Deleting job %s...' % fullname)
                os.remove(fullname)
        except:
            _logger.error('Error removing job transfer file!')

        # ---------------------------------------------------------------------
        # Log message:
        # ---------------------------------------------------------------------
        if industria_mrp_id:
            i40_pool.write_log_chatter_message(
                cr, uid, [industria_mrp_id],
                '[JOB] Annullato job di stesura, file: %s' % fullname
                , context=context)
        else:
            _logger.error('Job not linked in I40 Order: %s' % fullname)

        self.write(cr, uid, ids, {
            'state': 'DRAFT',
            'ended_at': False,
        }, context=context)

    def completed_fabric_job(self, cr, uid, ids, context=None):
        """ Send job to tender
        """
        job_id = ids[0]
        database_pool = self.pool.get('industria.database')
        i40_pool = self.pool.get('industria.mrp')

        if context is None:
            context = {}

        industria_mrp_id = False
        fullname = 'NON TROVATO'
        try:
            # Delete file if present:
            job = self.browse(cr, uid, job_id, context=context)
            industria_mrp_id = job.industria_mrp_id.id

            fullname = self.get_make_filename(job)
            history_fullname = os.path.join(
                # Make path + /fatti
                os.path.dirname(fullname), 'fatti',
                # Make filename + datetime.log
                '%s.%s.log' % (
                    os.path.basename(fullname),
                    str(datetime.now()).replace(':', '_').replace('/', '_')
                )
            )
            if os.path.isfile(fullname):
                _logger.warning('Moving job %s > %s ...' % (
                    fullname, history_fullname))
                shutil.move(fullname, history_fullname)
        except:
            _logger.error('Error removing job transfer file!')

        # ---------------------------------------------------------------------
        # Log message:
        # ---------------------------------------------------------------------
        if industria_mrp_id:
            i40_pool.write_log_chatter_message(
                cr, uid, [industria_mrp_id],
                '[JOB] Fine job di stesura / taglio, file: %s' % fullname
                , context=context)
        else:
            _logger.error('Job not linked in I40 Order: %s' % fullname)

        self.write(cr, uid, ids, {
            'ended_at': datetime.now().strftime(
                DEFAULT_SERVER_DATETIME_FORMAT),
            'state': 'COMPLETED',
        }, context=context)

        # Generate pickings for load and unload materials:
        ctx = context.copy()
        ctx['force_job_id'] = job_id
        ctx['default_dep_mode'] = 'cut'
        return database_pool.generate_fabric_picking_from_job(
            cr, uid, False, context=ctx)

    def error_fabric_job(self, cr, uid, ids, context=None):
        """ Send job to tender
        """
        self.write(cr, uid, ids, {
            'state': 'ERROR',
        }, context=context)

    def force_opcua_job_closed(self, cr, uid, ids, context=None):
        """ Force job as completed
        """
        self.write(cr, uid, ids, {
            'state': 'COMPLETED',
        }, context=context)

    def button_print_job_report(self, cr, uid, ids, context=None):
        """ Redirect to report passing parameters
        """
        wiz_proxy = self.browse(cr, uid, ids)[0]

        datas = {}
        report_name = 'job_report_industria'
        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
        }

    def send_opcua_job(self, cr, uid, ids, context=None):
        """ Send job to robot
        """
        def get_value(parameter):
            value = parameter.value
            out_type = parameter.opcua_id.type
            if out_type == 'float':
                return float(value.replace(',', '.')) or 0.0
            elif out_type == 'integer':
                return int(value) or 0
            else:
                return str(value or '')

        def get_ascii(value):
            res = ''
            for c in value:
                if ord(c) < 127:
                    res += c
                else:
                    res += '.'
            return str(res)

        if context is None:
            context = {}

        # pdb.set_trace()
        database_pool = self.pool.get('industria.database')
        production_pool = self.pool.get('industria.production')
        source_pool = self.pool.get('industria.robot')

        # Read parameter data:
        job_id = ids[0]
        job = self.browse(cr, uid, job_id, context=context)
        database = job.database_id
        program = job.program_id
        source = job.source_id
        robot = database_pool.get_robot(database)

        # =====================================================================
        # 1. Send to OVEN BOX:
        # =====================================================================
        robot_site_code = source.site_code or ''
        robot_ref_code = source.ref_code or ''
        cabin_call = database_pool.get_flask_sql_call(
            cr, uid, database, context=context)
        if cabin_call:
            # -----------------------------------------------------------------
            # 1. Check if job is present:
            # -----------------------------------------------------------------
            url, headers, payload = cabin_call  # Extract 3 parameter

            # Extend call params:
            payload['params']['command'] = 'mysql_select'
            payload['params']['query'] = \
                'SELECT * FROM siord00f WHERE SIORDNUM = %s;' % job_id

            response = requests.post(
                url, headers=headers, data=json.dumps(payload))
            response_json = response.json()
            job_present = False
            if response_json['success']:
                record = response_json.get('reply', {}).get('record', [])
                if record:
                    job_present = True
                    # todo update if needed?
            else:
                raise osv.except_osv(
                    _('Cabina:'),
                    _('La cabina non risponde (o la macchina di servizio)!'))

            # -----------------------------------------------------------------
            # 2. Create new job:
            # -----------------------------------------------------------------
            if not job_present:
                # Setup data used for timestamp and deadline (for now)
                now = datetime.now()
                now_text = str(now)

                # Extract detail for insert job:
                job_detail = ''
                for product in job.product_ids:
                    job_detail += '%s - Pz %s\n' % (
                        product.product_id.default_code or '',
                        product.piece,
                    )
                job_detail = job_detail[:500]  # Limit of char

                # oven_pre_job_ids  for mrp_id
                job_color_code = job.color   # 'BI'
                job_color = job_color_code   # todo convert as 'Bianco'?
                job_deadline = now_text[:10]  # todo deadline
                job_sequence = 10  # todo priority
                state = '7'  # to be sent

                # Override previous call params:
                payload['params']['command'] = 'mysql_insert'
                payload['params']['query'] = '''
                    INSERT INTO siord00f(
                        SIORDANN, SIORDNUM, SIORDSTA,
                        SIORDDAT, SIORDORA,
                        SIORDDESC, SIORDCCOL, SIORDCOL,
                        SIORDDPI, SIORDSEQ,
                        SIORDCIMP, SIORDCSED
                        )
                    VALUES (
                        %s, %s, '%s',
                        '%s', '%s',
                        '%s', '%s', '%s',
                        '%s', '%s',
                        '%s', '%s'                        
                        );
                    ''' % (
                    now.year, job_id, state,
                    now_text[:10], now_text[11:19],
                    job_detail, job_color_code, job_color,

                    # Deadline:
                    job_deadline, job_sequence,
                    robot_site_code, robot_ref_code,
                )

                response = requests.post(
                    url, headers=headers, data=json.dumps(payload))
                response_json = response.json()
                if response_json['success']:
                    # record_id not used for now (use Job ID for key link)
                    record_id = response_json.get(
                        'reply', {}).get('id', 'ID Non trovato')
                else:
                    _logger.error(
                        response_json.get('reply', {}).get(
                            'error', 'Errore collegandosi alla macchina'))
        # todo if error remove also from oven

        # =====================================================================
        # 2. Send to OVEN:
        # =====================================================================
        mask = source.opcua_mask

        # Get free program:
        production_ids = production_pool.search(cr, uid, [
            ('ref', '>', 0),  # XXX exclude 0
            ], context=context)
        opcua_ref = 0
        for production in production_pool.browse(
                cr, uid, production_ids, context=context):
            if not production.name:
                opcua_ref = production.ref
                break

        if not opcua_ref:
            raise osv.except_osv(
                _('Errore commessa'),
                _('Impossibile creare commesse, il numero massimo è stato '
                  'raggiunto, chiuderne qualcuna e riprovare'))

        # Program parameter:
        for parameter in program.parameter_ids:
            command_text = get_ascii(mask % (
                    parameter.opcua_id.name,
                    opcua_ref
                ))
            _logger.info('OPCUA get: %s' % command_text)
            database_pool.set_data_value(
                robot,
                command_text,
                get_value(parameter),
            )

        # Header parameter:
        database_pool.set_data_value(
            robot,
            mask % ('Commessa', opcua_ref),
            get_ascii(job.force_name or ('Job #%s' % job.id)),
        )
        database_pool.set_data_value(
            robot,
            mask % ('Colore', opcua_ref),
            get_ascii(job.color or 'Non definito'),
        )

        # Reload this ref production (link to this job_id:
        context_forced = context.copy()
        context_forced['reload_only_ref'] = opcua_ref
        context_forced['force_job_id'] = ids[0]

        source_pool.button_load_production_from_robot(cr, uid, [
            source.id,
        ], context=context_forced)

        try:
            robot.disconnect()
        except:
            _logger.error('Error disconnecting robot OPCUA!\n{}'.format(
                sys.exc_info(),
            ))
        _logger.info('Send data to robot...')
        return self.write(cr, uid, ids, {
            'state': 'RUNNING',
        }, context=context)

    def _get_duration(self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            created_at = record.created_at
            ended_at = record.ended_at
            if created_at and ended_at:
                duration = datetime.strptime(
                    ended_at, DEFAULT_SERVER_DATETIME_FORMAT) - \
                           datetime.strptime(
                               created_at, DEFAULT_SERVER_DATETIME_FORMAT)
                # / 60.0 (use minute instead of hours
                duration = duration.seconds / 60.0
            else:
                duration = False
            res[record.id] = duration
        return res

    _columns = {
        # todo remove?
        'out_statistic': fields.boolean(
            'Fuori statistica', help='Job durato oltre il tempo di allarme'),
        'dismiss': fields.boolean(
            'Job non completo', help='Job non completo, errore'),
        'unused': fields.boolean(
            'Non usato per il magazzino',
            help='Job nun utilizzato per il magazzino, non verrà collegato al '
                 'picking'),
        'created_at': fields.datetime('Inizio'),
        'ended_at': fields.datetime('Fine'),
        'updated_at': fields.datetime('Modifica'),
        # TODO duration seconds?

        'force_name': fields.char('Forza nome', size=30),
        'color': fields.char('Colore', size=20),
        'industria_ref': fields.integer('ID rif.'),
        'label': fields.integer(
            'Etichette',
            help='Usate per generare l\'elenco etichette in stampa'),
        'has_label': fields.boolean('Con stampa etichette'),
        'program_id': fields.many2one(
            'industria.program', 'Programma'),
        'database_id': fields.many2one(
            'industria.database', 'Database'),
        'source_id': fields.many2one(
            'industria.robot', 'Robot'),
        'partner_id': fields.related(
            'source_id', 'partner_id',
            type='many2one', relation='res.partner',
            string='Supplier', store=True),
        'force_product_id': fields.many2one(
            'product.product', 'Prodotto'),

        'state': fields.selection([
            ('DRAFT', 'Bozza'),
            ('ERROR', 'Errore'),
            ('RUNNING', 'In esecuzione'),
            ('COMPLETED', 'Completato'),
            ], 'State', required=True),
        'notes': fields.text('Note'),
        'job_duration': fields.function(
            _get_duration, method=True,
            type='float', string='Durata',
            store={
                'industria.job': (
                    lambda self, cr, uid, ids, ctx=None: ids,
                    ['create_at', 'ended_at'],
                    10,
                )}),
        'duration': fields.float('Durata', digits=(10, 3)),
        'duration_stop': fields.float('Durata fermo', digits=(10, 3)),
        'duration_change': fields.float(
            'Durata approntamento', digits=(10, 3)),
        'picking_id': fields.many2one(
            'stock.picking', 'Picking',
            help='When generate a picking for stock movement will be linked '
                 'here'),
        'production_id': fields.many2one(
            'industria.production', 'OPCUA production'),
        'piece': fields.integer('Total piece x job'),
        'piece1_start': fields.integer(
            'Fondo scala pezzi',
            help='Totale pezzi fondo scala del primo record'),
        'bar': fields.integer('Totale barre', help='Usate per taglia tubi'),
        'product_ids': fields.one2many(
            'industria.job.product', 'job_id', 'Prodotti'),
    }

    _defaults = {
        'state': lambda *x: 'DRAFT',
        'piece': lambda *x: 1,
        'label': lambda *x: 1,
        'created_at': lambda *d: ('%s' % datetime.now())[:19],
    }


class IndustriaJobStep(orm.Model):
    """ Model name: Industria Job fabric
        Field name keep as in MySQL for fast import
    """

    _name = 'industria.job.step'
    _description = 'Job step'
    _rec_name = 'sequence'
    _order = 'sequence'

    _columns = {
        'name': fields.integer('Nome'),
        'sequence': fields.integer('Sequenza'),
        'job_id': fields.many2one('industria.job', 'Job', ondelete='cascade'),
        'program_id': fields.many2one('industria.program', 'Programma'),
    }


class IndustriaJobFabric(orm.Model):
    """ Model name: Industria Job fabric
        Field name keep as in MySQL for fast import
    """

    _name = 'industria.job.fabric'
    _description = 'Job tessuti'
    _rec_name = 'sequence'
    _order = 'sequence'

    _columns = {
        'sequence': fields.integer('Seq.'),
        'step_id': fields.many2one(
            'industria.job.step', 'Step', ondelete='cascade'),
        'fabric_id': fields.many2one(
            'product.product', 'Tessuto', required=True),
        'total': fields.integer('Totale', required=True),
    }


class IndustriaJobFabricProduct(orm.Model):
    """ Model name: Industria Job fabric product
    """

    _name = 'industria.job.fabric.product'
    _description = 'Job product under fabric'
    _rec_name = 'product_id'

    _columns = {
        'fabric_id': fields.many2one(
            'industria.job.fabric', 'Strato', ondelete='cascade'),
        'product_id': fields.many2one(
            'product.product', 'Semilavorato', required=True),
        'total': fields.integer('Totale', required=True),
    }


class IndustriaJobStepInherit(orm.Model):
    """ Model name: Industria Job fabric
        Field name keep as in MySQL for fast import
    """

    _inherit = 'industria.job.step'

    _columns = {
        'fabric_ids': fields.one2many(
            'industria.job.fabric', 'step_id', 'Tessuti')
    }


class IndustriaRobotRelation(orm.Model):
    """ Model name: Industria Robot Relations
    """

    _inherit = 'industria.robot'

    _columns = {
        'program_ids': fields.one2many(
            'industria.program', 'source_id', 'Program'),
        'job_ids': fields.one2many(
            'industria.job', 'source_id', 'Job'),
    }


class ProductProduct(orm.Model):
    """ Model name: Product
    """

    _inherit = 'product.product'

    def get_oven_component_colored(
            self, cr, uid, origin, color, robot_id, context=None):
        """ Duplicate product passed with new format
        """
        if type(origin) == int:
            origin = self.browse(cr, uid, origin, context=context)
        origin_id = origin.id
        new_code = '%s.%s' % (origin.default_code, color)
        new_name = '%s Colore %s' % (origin.name, color)

        new_ids = self.search(cr, uid, [
            ('default_code', '=', new_code),
            # todo search also extra fields industria_semiproduct? robot_id?
        ], context=context)
        if new_ids:
            return new_ids[0]  # yet created
        new_id = self.copy(cr, uid, origin_id, default={
            'default_code': new_code,
            'name': new_name,
            'relative_type': 'half',
            'industria_in_id': robot_id,  # Default input for this robot
            'industria_semiproduct': True,  # todo needed?
        }, context=context)

        # Generate BOM for half product:
        self.create_product_half_bom(cr, uid, [new_id], context=context)
        new = self.browse(cr, uid, new_id, context=context)

        # Add component in BOM:
        bom_pool = self.pool.get('mrp.bom.line')
        bom_pool.create(cr, uid, {
            'bom_id': new.half_bom_id.id,
            'product_id': origin_id,
            'product_qty': 1.0,  # Take original
            'halfwork_id': new_id,
            # todo add extra component for powder
        }, context=context)
        return new_id

    _columns = {
        'oven_lot': fields.integer(
            'Lotto verniciatura',
            help='Lotto della rastrelliera di quando il prodotto va in '
                 'verniciatura (usato per calcolare il numero etichette '
                 'durante la stampa lavorazione)'),
        'industria_semiproduct': fields.boolean(
            'Semilavorato I40',
            help='Indica che il prodotto è un semilavorato dei processi di '
                 'Industria 4.0 (creato automaticamente)'),

        # todo needed?
        'industria_in_id': fields.many2one(
            'industria.robot', 'Ingresso',
            help='Semilavorato in ingresso di questo robot'),
        'industria_out_id': fields.many2one(
            'industria.robot', 'Uscita',
            help='Semilavorato in uscita di questo robot'),
        }


class ResPartner(orm.Model):
    """ Model name: Res Partner
    """

    _inherit = 'res.partner'

    _columns = {
        'program_ids': fields.one2many(
            'industria.program', 'partner_id', 'Program'),
        'source_ids': fields.one2many(
            'industria.robot', 'partner_id', 'Robot'),
    }


class StockPicking(orm.Model):
    """ Update stock picking
    """

    _inherit = 'stock.picking'

    _columns = {
        'job_ids': fields.one2many(
            'industria.job', 'picking_id', 'Jobs'),
    }


class IndustriaDatabaseInherit(orm.Model):
    """ Model name: Industria Database inherit
    """
    _inherit = 'industria.database'

    _columns = {
        'robot_ids': fields.one2many(
            'industria.robot', 'database_id', 'Robot'),
    }


class IndustriaProgramInherit(orm.Model):
    """ Model name: Industria Program
    """

    _inherit = 'industria.program'

    _columns = {
        'parameter_ids': fields.one2many(
            'industria.program.parameter', 'program_id',
            string='Parametri'),
        'fabric_ids': fields.one2many(
            'industria.program.fabric', 'program_id', 'Tessuti')
    }


class IndustriaJobInherit(orm.Model):
    """ Model name: Industria Job
        Field name keep as in MySQL for fast import
    """

    _inherit = 'industria.job'

    def realign_previous_state(self, cr, uid, ids, context=None):
        """ Realign previous link:
        """
        current_job = self.browse(cr, uid, ids, context=context)[0]
        source_id = current_job.source_id.id
        job_ids = self.search(cr, uid, [
            ('source_id', '=', source_id),
        ], order='created_at', context=context)

        previous_id = job_ids[0]
        for job_id in job_ids:
            self.write(cr, uid, [job_id], {
                'previous_id': previous_id,
            }, context=context)
            previous_id = job_id
        return True

    def _get_duration_extra_data(
            self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate extra data for compute duration
        """
        def date_difference(from_date, to_date):
            """ Calculate difference from date to date
            """
            if not from_date or not to_date:
                return 0.0

            delta = \
                datetime.strptime(to_date, DEFAULT_SERVER_DATETIME_FORMAT) - \
                datetime.strptime(from_date, DEFAULT_SERVER_DATETIME_FORMAT)
            return delta.seconds / 60.0  # return minutes

        block_job = 2  # 2 Job will be made once
        not_consider_value = 60  # sec.
        consider_change_total = True

        res = {}
        for job in self.browse(cr, uid, ids, context=context):
            previous = job.previous_id
            duration_not_considered = duration_need_setup = False
            if previous:
                # Check days jump
                last_program = [previous.program_id]
                if block_job == 2:
                    last_program.append(previous.previous_id.program_id)

                # Read extra data parameters:
                previous_from = previous.created_at
                previous_to = previous.ended_at
                current_from = job.created_at
                # current_to = job.ended_at  # not used

                duration_change_total = date_difference(
                    previous_from, current_from)
                duration_change_gap = date_difference(
                    previous_to, current_from)

                # Duration very long
                if duration_change_gap > not_consider_value:
                    duration_not_considered = True

                # New work job (setup needed only first change!)
                # todo and not previous.duration_need_setup (loop error)
                if job.program_id not in last_program:
                    duration_setup = duration_change_gap
                    # Not considered change when setup:
                    duration_change_total = 0.0
                    duration_change_gap = 0.0
                    duration_need_setup = True
                else:
                    duration_setup = 0.0
            else:
                duration_change_total = duration_change_gap = \
                    duration_setup = 0.0

            # Used when job has 2 block:
            if not consider_change_total:
                duration_change_total = 0.0

            res[job.id] = {
                'duration_change_total': duration_change_total,
                'duration_change_gap': duration_change_gap,
                'duration_setup': duration_setup,
                'duration_not_considered': duration_not_considered,
                'duration_need_setup': duration_need_setup,
            }
        return res

    def _function_get_fabric_layer(
            self, cr, uid, ids, fields, args, context=None):
        """ Fields function for calculate
        """
        res = {}
        for job in self.browse(cr, uid, ids, context=context):
            total = 0
            detail = ''
            for step in job.step_ids:
                fabric_length = step.program_id.fabric_length
                for fabric_line in step.fabric_ids:
                    layer = fabric_line.total
                    detail += '%s = %s mt  di %s \n' % (
                        layer,
                        int(round(layer * fabric_length / 1000.0, 0)),
                        fabric_line.fabric_id.default_code,
                    )
                    # Total work only first loop:
                    # Step are in this application the same total layer!
                    # so no need to repeat in total
                    # if not total:
                    total += layer

            res[job.id] = {
                'fabric_step': len(job.step_ids),
                'fabric_layer': total,
                'fabric_detail': detail,
            }
        return res

    _columns = {
        'fabric_step': fields.function(
            _function_get_fabric_layer, method=True,
            type='integer', string='Gradini', multi=True,
            store=False),
        'fabric_layer': fields.function(
            _function_get_fabric_layer, method=True,
            type='integer', string='Strati job', multi=True,
            store=False),
        'fabric_detail': fields.function(
            _function_get_fabric_layer, method=True, multi=True,
            type='char', string='Dettaglio',
            store=False),

        'previous_id': fields.many2one(
            'industria.job', 'Precedente'),

        'duration_change_total': fields.function(
            _get_duration_extra_data, method=True,
            type='float', string='Durata complessiva cambio',
            store=False, multi=True,
            help='Durata complessiva del cambio '
                 '(durata lav. successiva + gap tra le 2 lavorazioni),'
                 'durata attrezzaggio completa però la parte in cui'
                 'sta lavorando la lavorazione precedente non è importante'),
        'duration_change_gap': fields.function(
            _get_duration_extra_data, method=True,
            type='float', string='Durata influente del cambio',
            store=False, multi=True,
            help='Tempo morto tra due lavorazioni consecutive di solito dato '
                 'dal fatto che si inizia ad attrezzare la seconda mentre sta'
                 'girando la prima e quandi finisce la prima non si è ancora'
                 'ultimato il setup (gap puro!)'),
        'duration_setup': fields.function(
            _get_duration_extra_data, method=True,
            type='float', string='Durata attrezzaggio',
            store=False, multi=True,
            help='Durata complessiva tempo di riattezzaggio della macchina'
                 'considerando il cambio dime sul piano di lavoro'),
        'duration_not_considered': fields.function(
            _get_duration_extra_data, method=True,
            type='boolean', string='Non considerare la lavorazione',
            store=False, multi=True,
            help='Indica che è difficile capire i tempi dedotti '
                 'automaticamente perchè risultano gap troppo alti e non è '
                 'possibile fare ipotesi corrette sul perchè'),
        'duration_need_setup': fields.function(
            _get_duration_extra_data, method=True,
            type='boolean', string='Cambio lavorazione',
            store=False, multi=True,
            help='Questa lavorazione effettua un cambio rispetto alle 2 '
                 'precedenti ha quindi un setup da considerare maggiore'
                 'come tempo di approntamento macchinario'),

        'step_ids': fields.one2many(
            'industria.job.step', 'job_id', 'Gradini')
    }


class IndustriaProgramFabricInherit(orm.Model):
    """ Model name: Industria Program fabric
    """

    _inherit = 'industria.program.fabric'

    _columns = {
        'family_mode': fields.boolean(
            'Modalità famiglia',
            help='Se spuntato presenta le dime legate come famiglia e non '
                 'come elenco prodotti'),
        'part_ids': fields.one2many(
            'industria.program.fabric.part', 'fabric_id', 'Parti')
    }


class IndustriaJobFabricInherit(orm.Model):
    """ Model name: Industria Job Fabric
        Field name keep as in MySQL for fast import
    """

    _inherit = 'industria.job.fabric'

    _columns = {
        'product_ids': fields.one2many(
            'industria.job.fabric.product', 'fabric_id', 'Semilavorati')
    }
