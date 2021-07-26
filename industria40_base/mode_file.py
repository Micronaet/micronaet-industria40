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
        pdb.set_trace()
        database_id = ids[0]
        database = self.browse(cr, uid, database_id, context=context)
        path = os.path.expanduser(database.file_stat_path)
        for root, folders, files in os.walk(path):
            for filename in files:
                fullname = os.path.join(root, filename)

                file_ids = file_pool.search(cr, uid, [
                    ('name', '=', filename),
                    ('database_id', '=', database_id),
                ], context=context)
                if not file_ids:
                    timestamp = str(os.stat(fullname).st_mtime)
                    file_ids = [file_pool.create(cr, uid, {
                        'name': filename,
                        'fullname': fullname,
                        'database_id': database_id,
                        'timestamp': timestamp,
                        'row': 0,
                    }, context=context)]

                file_pool.load_file(
                    cr, uid, file_ids, fullname, context=context)
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
        program_pool = self.pool.get('industria.program')
        job_pool = self.pool.get('industria.job')

        separator = ';'
        file_id = ids[0]
        file = self.browse(cr, uid, file_id, context=context)
        fullname = file.fullname
        timestamp = str(os.stat(fullname).st_mtime)
        current_row = file.row
        row = 0
        last_line = False
        for line in open(fullname, 'r'):
            row += 1
            line.split(separator)
            if row <= current_row:
                last_program = line[3]
                continue  # yet read
            state = line[0]
            date = line[1]
            time = line[2]
            program_ref = line[3]
            # active1 active2 not used

            # Calculated:
            if last_program != program_ref:
                # todo Change job here
                pass

            program_id = False  # todo find
            job_id = False  # todo find
            data = {
                'name': program_ref,
                'timestamp': '%s-%s-%s %s' % (
                    date[:4], date[5:8], date[:2],
                    time,
                ),
                'piece1': line[4],
                'total1': line[5],
                'piece2': line[6],
                'total2': line[7],
                'duration_piece': line[8],
                'duration_bar': line[9],
                'program_id': program_id,
                'file_id': file_id,
                'job_id': job_id,
                'state': state,
            }
            self.create(cr, uid, data, context=context)

        self.write(cr, uid, ids, {
            'row': row,
            'timestamp': timestamp,
        }, context=context)

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
            _logger.warning('File %s has same timestamp, not reloaded')
            return False
        database = file.database_id
        # if not fullname:
        #    path = database.file_stat_path
        #    fullname = os.path.join(path, self.get_today_file(
        #        cr, uid, ids, context=context))

        if database.file_mode == 'csv':
            self.file_import_stat_csv(cr, uid, ids, context=context)
        elif database.file_mode == 'xml':
            self.file_import_stat_xml(cr, uid, ids, context=context)
        return True

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
