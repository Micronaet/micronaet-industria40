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


class IndustriaJob(orm.Model):
    """ Model name: Industria job
    """

    _inherit = 'industria.job'

    def open_file_stat_row(self, cr, uid, ids, context=None):
        """ Open list of imported row
        """
        stat_pool = self.pool.get('industria.pipe.file.stat')
        model_pool = self.pool.get('ir.model.data')

        job_id = ids[0]
        stat_ids = stat_pool.search(cr, uid, [
            ('job_id', '=', job_id),
        ], context=context)

        view_id = model_pool.get_object_reference(
            cr, uid,
            'industria40_base', 'view_industria_pipe_file_stat_tree')[1]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Result for view_name'),
            'view_type': 'form',
            'view_mode': 'tree',
            # 'res_id': 1,
            'res_model': 'industria.pipe.file.stat',
            'view_id': view_id,  # False
            'views': [(False, 'tree')],
            'domain': [('id', 'in', stat_ids)],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
        }


class IndustriaDatabase(orm.Model):
    """ Model name: Industria database
    """

    _inherit = 'industria.database'

    def load_all_stat_file(self, cr, uid, ids, context=None):
        """ Call every robot same action
        """
        robot_pool = self.pool.get('industria.robot')

        for robot in self.browse(cr, uid, ids, context=context)[0].robot_ids:
            robot_pool.load_all_stat_file(
                cr, uid, [robot.id], context=context)


class IndustriaRobot(orm.Model):
    """ Model name: Industria robot
    """

    _inherit = 'industria.robot'

    def get_today_file(self, cr, uid, ids, context=None):
        """ Estract filename for today log
        """
        database_id = ids[0]
        database = self.browse(cr, uid, database_id, context=context)
        mode = database.file_mode
        if mode == 'pipe':
            return datetime.now().strftime('%y_%m_%d.txt')
        elif mode == 'fabric':
            return datetime.now().strftime('%Y%m%d.xml')
        else:
            _logger.error('Not found default file!')
            return ''

    def load_all_stat_file(self, cr, uid, ids, context=None):
        """ Load all daily file from data folder
        """
        file_pool = self.pool.get('industria.robot.file')
        robot_id = ids[0]
        robot = self.browse(cr, uid, robot_id, context=context)
        database_id = robot.database_id.id
        path = os.path.expanduser(robot.file_stat_path)
        for root, folders, files in os.walk(path):
            for filename in files:
                fullname = os.path.join(root, filename)
                file_ids = file_pool.search(cr, uid, [
                    ('name', '=', filename),
                    ('robot_id', '=', robot_id),
                ], context=context)
                if not file_ids:
                    timestamp = str(os.stat(fullname).st_mtime)
                    file_ids = [file_pool.create(cr, uid, {
                        'name': filename,
                        'fullname': fullname,
                        'robot_id': robot_id,
                        'database_id': database_id,  # todo related!
                        # 'timestamp': timestamp,  # Not the first time!
                        'row': 0,
                    }, context=context)]

                file_pool.load_file(
                    cr, uid, file_ids, context=context)
            break  # No subfolders
        return True

    _columns = {
        'file_mode': fields.selection([
            ('fabric', 'Tessuti (XML)'),
            ('pipe', 'Tubi (csv)'),
        ], 'Mode', required=True),
        'file_stat_path': fields.text(
            'Cartella statistiche', help='Nella gestione DB con file'),
        'file_execute_path': fields.text(
            'Cartella job', help='Nella gestione DB con file'),
        # 'file_alarm_path': fields.text(
        #    'Cartella allarmi', help='Nella gestione DB con file'),
    }
    _defaults = {
        'file_mode': lambda *x: 'pipe',
    }


class IndustriaRobotFile(orm.Model):
    """ Model name: Industria fabric file
    """

    _name = 'industria.robot.file'
    _description = 'Industria robot file'
    _rec_name = 'name'
    _order = 'name desc'

    def file_import_stat_csv(self, cr, uid, ids, context=None):
        """ Import CSV file (pipe)
        """
        def clean_float(value):
            return float(value.replace('s', ''))
        def clean_integer(value):
            return int(value)
        def get_datetime(date, time):
            gmt_daylight = 2
            return '%s-%s-%s %s%s' % (
                date[-4:], date[3:5], date[:2],
                '%02d' % (int(time[:2]) - gmt_daylight),
                time[2:],
            )

        program_pool = self.pool.get('industria.program')
        job_pool = self.pool.get('industria.job')
        file_pool = self.pool.get('industria.pipe.file.stat')

        separator = ';'
        extension = 'txt'

        file_id = ids[0]
        file = self.browse(cr, uid, file_id, context=context)
        robot_id = file.robot_id.id
        database_id = file.database_id.id

        fullname = file.fullname
        if not fullname.endswith(extension):
            _logger.error('File: %s not used!' % fullname)
            return False

        timestamp = str(os.stat(fullname).st_mtime)
        current_row = file.row
        if current_row:  # Update last job found:
            last_job_id = job_id = file.last_job_id
            last_program_ref = file.last_program_ref  # todo not used!
            job = job_pool.browse(cr, uid, last_job_id, context=context)
            program_id = job.program_id.id

            # Total till now for last job:
            job_piece1_start = job.piece1
            job_bar_counter = job.bar

        else:
            last_job_id = last_program_ref = False

        last_record_date = False
        counter = 0
        for line in open(fullname, 'r'):
            if not counter:
                counter += 1
                continue
            counter += 1
            line = line.strip()
            if not line:
                continue  # Jump empty line
            row = line.split(separator)

            # Read need fields:
            program_ref = row[3]
            date = row[1]
            time = row[2]
            piece1 = clean_integer(row[4])

            record_date = get_datetime(date, time)

            if counter <= current_row:
                last_record_date = record_date  # Save last record date
                last_program_ref = program_ref
                continue  # yet read

            # Read remain fields:
            state = row[0]
            # active1 active2 not used

            # Calculated:
            if last_program_ref != program_ref:
                # Get program_id:
                program_ids = program_pool.search(cr, uid, [
                    ('source_id', '=', robot_id),
                    ('name', '=', program_ref),
                ], context=context)
                if program_ids:
                    program_id = program_ids[0]
                else:
                    program_id = program_pool.create(cr, uid, {
                        'code': program_ref,
                        'name': program_ref,
                        'source_id': robot_id,
                        'database_id': database_id,
                        # 'product_id': False,
                        # 'partner_id': ,
                        # 'mode':
                        # 'note':
                        # 'medium'
                        # 'over_alarm'
                    }, context=context)

                # Get new job:
                job_piece1_start = piece1
                job_id = job_pool.create(cr, uid, {
                    'created_at': record_date,
                    # 'updated_at': 'ended_at':
                    # 'duration':
                    # 'duration_stop':
                    # 'duration_change':

                    'program_id': program_id,
                    'database_id': database_id,
                    'source_id': robot_id,
                    'state': 'RUNNING',
                    # 'force_product_id': ,
                    # 'DRAFT' 'ERROR' 'RUNNING' 'COMPLETED'
                    # 'notes'
                    # 'job_duration':
                    # 'picking_id':

                    # 'production_id':
                    # 'piece'
                    # 'product_ids'

                    # 'out_statistic':
                    # 'dismiss'
                    # 'unused'
                    # 'partner_id':
                }, context=context)
                if last_job_id:
                    # Mark as completed:
                    job_pool.write(cr, uid, [last_job_id], {
                        'state': 'COMPLETED',
                        'updated_at': last_record_date,
                        'ended_at': last_record_date,
                        'piece': piece1 - job_piece1_start,
                        'bar': job_bar_counter,

                        # todo Update statistic data?
                        # 'out_statistic': 'dismiss' 'unused' 'job_duration'
                        # todo Update production
                        # 'picking_id': 'production_id': 'piece' 'product_ids'

                    }, context=context)

                job_bar_counter = 0

                # Last data:
                last_job_id = job_id
                last_program_ref = program_ref

            if state == 'CAMBIO BARRA':
                job_bar_counter += 1
            data = {
                'name': program_ref,
                'timestamp': record_date,
                'piece1': piece1,
                'total1': clean_integer(row[5]),
                'piece2': clean_integer(row[6]),
                'total2': clean_integer(row[7]),
                'duration_piece': clean_float(row[8]),
                'duration_bar': clean_float(row[9]),
                'program_id': program_id,
                'file_id': file_id,
                'job_id': job_id,
                'state': state,
            }
            file_pool.create(cr, uid, data, context=context)
            last_record_date = record_date
            # todo counter pieces

        # ---------------------------------------------------------------------
        # Update last job:
        # ---------------------------------------------------------------------
        if last_job_id:
            # Mark as completed:
            job_pool.write(cr, uid, [last_job_id], {
                'state': 'COMPLETED',
                'updated_at': last_record_date,
                'ended_at': last_record_date,
                'piece': piece1 - job_piece1_start,
                'bar': job_bar_counter,

                # todo Update statistic data?
                # 'out_statistic': 'dismiss' 'unused' 'job_duration'
                # todo Update production
                # 'picking_id': 'production_id': 'piece' 'product_ids'

            }, context=context)

        # ---------------------------------------------------------------------
        # Update reference for file:
        # ---------------------------------------------------------------------
        self.write(cr, uid, ids, {
            'row': counter,
            'timestamp': timestamp,
            'last_program_ref': last_program_ref,
            'last_job_id': last_job_id,
        }, context=context)
        _logger.info('File %s loaded' % fullname)
        return True

    def file_import_stat_xml(self, cr, uid, ids, context=None):
        """ Import CSV file (fabric)
        """
        file_id = ids[0]
        file = self.browse(cr, uid, file_id, context=context)
        fullname = file.fullname
        return True

    def load_file(self, cr, uid, ids, context=None):
        """ Load daily file from data folder
        """
        file_id = ids[0]
        file = self.browse(cr, uid, file_id, context=context)
        fullname = file.fullname
        if file.timestamp == str(os.stat(fullname).st_mtime):
            _logger.warning(
                'File %s has same timestamp, not reloaded' % fullname)
            return False

        robot = file.robot_id
        # if not fullname:
        #    path = database.file_stat_path
        #    fullname = os.path.join(path, self.get_today_file(
        #        cr, uid, ids, context=context))

        if robot.file_mode == 'pipe':  # csv
            self.file_import_stat_csv(cr, uid, ids, context=context)
        elif robot.file_mode == 'fabric':  # xml
            self.file_import_stat_xml(cr, uid, ids, context=context)
        return True

    def open_file_stat_row(self, cr, uid, ids, context=None):
        """ Open list of imported row
        """
        stat_pool = self.pool.get('industria.pipe.file.stat')
        model_pool = self.pool.get('ir.model.data')

        file_id = ids[0]
        stat_ids = stat_pool.search(cr, uid, [
            ('file_id', '=', file_id),
        ], context=context)

        view_id = model_pool.get_object_reference(
            cr, uid,
            'industria40_base', 'view_industria_pipe_file_stat_tree')[1]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Result for view_name'),
            'view_type': 'form',
            'view_mode': 'tree',
            # 'res_id': 1,
            'res_model': 'industria.pipe.file.stat',
            'view_id': view_id,  # False
            'views': [(False, 'tree')],
            'domain': [('id', 'in', stat_ids)],
            'context': context,
            'target': 'current',  # 'new'
            'nodestroy': False,
            }

    _columns = {
        'name': fields.char('Nome file', size=40),
        'fullname': fields.char('Nome file', size=180),
        'timestamp': fields.char(
            'Data ora',
            size=40,
            help='Date e ora del file per sapere se è sato modificato dalla '
                 'ultima lettura'),
        'row': fields.integer('Riga', help='Ultima riga analizzata'),
        'robot_id': fields.many2one(
            'industria.robot', 'Robot'),
        'database_id': fields.many2one(  # todo related
            'industria.database', 'Database'),
        # Last reference_

        'last_program_ref': fields.char(
            'Ultimo rif. programma',
            help='Per tenere lo storico delle letture parziali'),
        'last_job_id': fields.integer(
            'Ultimo ID job',
            help='Per tenere lo storico delle letture parziali')
    }

    _defaults = {
        'state': lambda *x: 'DRAFT',
    }


class IndustriaPipeFileStat(orm.Model):
    """ Model name: Industria fabric file stat
    """

    _name = 'industria.pipe.file.stat'
    _description = 'Industria Fabric stat'
    _rec_name = 'timestamp'
    _order = 'timestamp desc'

    _columns = {
        'name': fields.char('Nome programma', size=30),
        'timestamp': fields.datetime('Timestamp'),
        'piece1': fields.integer('Pezzi (1)'),
        'total1': fields.integer('Su totale (1)'),
        'piece2': fields.integer('Pezzi (2)'),
        'total2': fields.integer('Su totale (2)'),
        'duration_piece': fields.float('Durata pezzo', digits=(10, 4)),
        'duration_bar': fields.float('Durata barra', digits=(10, 4)),
        'program_id': fields.many2one(
            'industria.program', 'Programma'),
        'file_id': fields.many2one(
            'industria.robot.file', 'File'),
        'job_id': fields.many2one(
            'industria.job', 'Job'),
        'state': fields.selection([
            ('STOP', 'Stop'),
            ('TAGLIO', 'Taglio'),
            ('CAMBIO BARRA', 'Cambio barra'),
        ], 'State', required=True),
        }


class IndustriaFabricFileStat(orm.Model):
    """ Model name: Industria fabric file stat
    """

    _name = 'industria.fabric.file.stat'
    _description = 'Industria Fabric stat'
    _rec_name = 'name'
    _order = 'create, name'

    _columns = {
        'name': fields.char('Rif. job', size=30),
        'ref': fields.char('Rif.', size=10),
        # Sent job ID
        'shape': fields.integer(
            'Totale forme', help='Totale forme del taglio'),
        'file_id': fields.many2one(
            'industria.robot.file', 'File'),
        'job_id': fields.many2one(
            'industria.job', 'Job'),
        'program_id': fields.many2one(
            'industria.program', 'Programma'),
        'fullname': fields.char('Nome file', size=90),
        'create': fields.datetime('Creazione'),
        'modify': fields.datetime('Modify'),
        'state': fields.selection([
            ('None', 'Nessuno'),  # Anomalia
            ('Preparation', 'Preparazione'),  # A. In preparazione iniziale
            ('Collimation', 'Collimazione'),  # B. Taratura post preparazione
            ('Simulation', 'Simulazione'),  # C. Simulazione dopo collimazione
            ('Cutting', 'Taglio'),  # D. In taglio
            ('Pending', 'Pendente'),  # E1 Fermato (tutti i casi extra)
            ('Completed', 'Completato'),  # E1. Terminato
            ('Aborted', 'Annullato'),  # E2. Annullato (si può riprendere?)
        ], 'State', required=True),
        'notes': fields.text('Note'),
        }

    _default = {
        'stat': lambda *x: 'None',
    }

    # 'last_record_id': fields.many2one(
    #    'industria.fabric.file.stat', 'Ultimo record creato'),
    #    'industria.pipe.file.stat', 'Ultimo record creato'),
