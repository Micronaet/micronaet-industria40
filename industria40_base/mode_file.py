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

    def get_today_file(self, cr, uid, ids, context=None):
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

    def file_import_stat_csv(self, cr, uid, ids, fullname, context=None):
        """ Import CSV file (pipe)
        """
        return True

    def file_import_stat_xml(self, cr, uid, ids, fullname, context=None):
        """ Import CSV file (fabric)
        """
        return True

    def load_daily_file(self, cr, uid, ids, fullname, context=None):
        """ Load daily file from data folder
        """
        database_id = ids[0]
        database = self.browse(cr, uid, database_id, context=context)
        if not fullname:
            path = database.file_stat_path
            fullname = os.path.join(path, self.get_today_file(
                cr, uid, ids, context=context))
        if database.file_mode == 'csv':
            self.file_import_stat_csv(cr, uid, ids, fullname, context=context)
        return True

    def load_all_stat_file(self, cr, uid, ids, context=None):
        """ Load all daily file from data folder
        """
        pdb.set_trace()
        database_id = ids[0]
        database = self.browse(cr, uid, database_id, context=context)
        path = database.file_stat_path
        for root, folders, files in os.walk(path):
            for filename in files:
                fullname = os.path.join(root, filename)
                self.load_daily_file(cr, uid, ids, fullname, context=context)
            break  # No subfolders

        return True

    _columns = {
        'file_mode': fields.selection([
            ('fabric', 'Tessuti (XML)'),
            ('pipe', 'Tubi (csv)'),
        ], 'Mode', required=True),
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

    _columns = {
        'name': fields.char('Nome file', size=40),
        'datetime': fields.char(
            'Data ora',
            size=40,
            help='Date e ora del file per sapere se è sato modificato dalla '
                 'ultima lettura'),
        'row': fields.integer('Riga', help='Ultima riga analizzata'),
        'database_id': fields.many2one(
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
