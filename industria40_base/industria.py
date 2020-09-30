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
import sys
import logging
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)


class IndustriaDatabase(orm.Model):
    """ Model name: Industria Database
    """
    _name = 'industria.database'
    _description = 'Database PC'
    _rec_name = 'name'
    _order = 'name'

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

        database = self.browse(cr, uid, ids, context=context)[0]
        connection = self.mssql_connect(cr, uid, ids, context=context)
        cursor = connection.cursor()

        try:
            query = """
                SELECT *  
                FROM programs
                """
            cursor.execute(query)
        except:
            raise osv.except_osv(
                _('Error SQL access'),
                'Executing query %s: \n%s' % (
                    query,
                    sys.exc_info(),
                ))

        partner_id = database.partner_id.id
        for record in cursor:
            industria_ref = record['id']
            data = {
                'industria_ref': industria_ref,
                'code': record['name'],
                'name': record['description'],
                'piece': record['npieces'],
                'timeout': record['maxexecutiontime'],
                # TODO created_at | updated_at
            }

            program_ids = program_pool.search(cr, uid, [
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

        database = self.browse(cr, uid, ids, context=context)[0]
        connection = self.mssql_connect(cr, uid, ids, context=context)
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

        partner_id = database.partner_id.id
        database_id = ids[0]
        for record in cursor:
            industria_ref = record['id']
            data = {
                'industria_ref': industria_ref,
                'ip': record['ip'],
                'name': record['description'] or record['name'],
                'partner_id': partner_id,
                'database_id': database_id,
            }

            robot_ids = robot_pool.search(cr, uid, [
                ('database_id', '=', database_id),
                ('industria_ref', '=', industria_ref),
            ], context=context)

            if robot_ids:
                robot_pool.write(
                    cr, uid, robot_ids, data, context=context)
            else:
                robot_pool.create(
                    cr, uid, data, context=context)
        return True

    def import_job(self, cr, uid, ids, context=None):
        """ Update job list
        """
        # TODO create context from ID (partial run)
        job_pool = self.pool.get('industria.job')
        robot_pool = self.pool.get('industria.robot')

        database = self.browse(cr, uid, ids, context=context)[0]
        connection = self.mssql_connect(cr, uid, ids, context=context)
        cursor = connection.cursor()

        try:
            query = """
                SELECT *  
                FROM jobs
                """
            cursor.execute(query)
        except:
            raise osv.except_osv(
                _('Error SQL access'),
                'Executing query %s: \n%s' % (
                    query,
                    sys.exc_info(),
                ))

        partner_id = database.partner_id.id
        for record in cursor:
            industria_ref = record['id']
            program_id = record['source_id']
            source_id = record['program_id']
            # TODO search source and program

            # state | notes | created_at | updated_at | ended_at
            data = {
                'industria_ref': industria_ref,
                # TODO check correct format
                'created_at': record['created_at'],
                'updated_at': record['updated_at'],
                'ended_at': record['ended_at'],

                'source_id': source_id,
                'program_id': program_id,
                'state': record['state'],
            }

            job_ids = job_pool.search(cr, uid, [
                ('industria_ref', '=', industria_ref),
            ], context=context)
            if job_ids:
                job_pool.write(
                    cr, uid, job_ids, data, context=context)
            else:
                job_pool.create(
                    cr, uid, data, context=context)
        return True

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'partner_id': fields.many2one(
            'res.partner', 'Supplier', required=True),
        'ip': fields.char('IP address', size=15),
        'username': fields.char('Username', size=64, required=True),
        'password': fields.char('Password', size=64, required=True),
        'database': fields.char('Database', size=64, required=True),
        'port': fields.integer('Port', required=True),
        'note': fields.text('Note'),
        'mode': fields.selection([
            ('mysql', 'My SQL'),
            ('mssql', 'MS SQL'),
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

    _columns = {
        'ip': fields.char('IP address', size=15),
        'name': fields.char('Name', size=64, required=True),
        'industria_ref': fields.integer('Industria ref key'),
        'partner_id': fields.many2one(
            'res.partner', 'Supplier', required=True),
        'database_id': fields.many2one(
            'industria.database', 'Database'),
        'note': fields.text('Note'),
    }


class IndustriaProgram(orm.Model):
    """ Model name: Industria Program
    """

    _name = 'industria.program'
    _description = 'Programs'
    _rec_name = 'name'
    _order = 'name'

    _columns = {
        'code': fields.char('Code', size=12),
        'name': fields.char('Name', size=64, required=True),
        'industria_ref': fields.integer('Industria ref key'),
        'timeout': fields.integer('Timeout'),
        'piece': fields.integer('Total piece x job'),
        'robot_id': fields.many2one(
            'industria.robot', 'Robot'),
        'partner_id': fields.related(
            'robot_id', 'partner_id',
            type='many2one', relation='res.partner',
            string='Supplier', store=True),
        'note': fields.text('Note'),
    }


class IndustriaJob(orm.Model):
    """ Model name: Industria Job
        Field name keep as in MySQL for fast import
    """

    _name = 'industria.job'
    _description = 'Jobs'
    _rec_name = 'created_at'
    _order = 'created_at desc'

    _columns = {
        'created_at': fields.datetime('Start'),
        'ended_at': fields.datetime('End'),
        'updated_at': fields.datetime('Modify'),
        # TODO duration seconds?

        'industria_ref': fields.integer('Industria ref key'),

        'program_id': fields.many2one(
            'industria.program', 'Program'),
        'source_id': fields.many2one(
            'industria.robot', 'Source Robot'),
        'partner_id': fields.related(
            'robot_id', 'partner_id',
            type='many2one', relation='res.partner',
            string='Supplier', store=True),
        'state': fields.selection([
            ('ERROR', 'Error'),
            ('RUNNING', 'Running'),
            ('COMPLETED', 'Completed'),
            ], 'State', required=True),
        'notes': fields.text('Note'),
    }

    _defaults = {
        'state': lambda *x: 'RUNNING',
    }


class IndustriaRobotRelation(orm.Model):
    """ Model name: Industria Robot Relations
    """

    _inherit = 'industria.robot'

    _columns = {
        'program_ids': fields.one2many(
            'industria.program', 'robot_id', 'Program'),
        'job_ids': fields.one2many(
            'industria.job', 'source_id', 'Job'),

    }


class ResPartner(orm.Model):
    """ Model name: Res Partner
    """

    _inherit = 'res.partner'

    _columns = {
        'program_ids': fields.one2many(
            'industria.program', 'partner_id', 'Program'),
        'robot_ids': fields.one2many(
            'industria.robot', 'partner_id', 'Robot'),
    }
