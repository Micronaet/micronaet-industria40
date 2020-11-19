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
    """ Model name: Industria Database
    """
    _name = 'industria.database'
    _description = 'Database PC'
    _rec_name = 'name'
    _order = 'name'

    def update_medium_program_job(self, cr, uid ,ids, context=None):
        """ Update medium
        """
        job_pool = self.pool.get('industria.job')
        job_ids = job_pool.search(cr, uid, [
            (''),
        ], context=context)
        for job in
    def generate_picking_from_job(self, cr, uid, ids, context=None):
        """ Generate picking from jobs
        """
        model_pool = self.pool.get('ir.model.data')
        picking_pool = self.pool.get('stock.picking')
        move_pool = self.pool.get('stock.move')
        job_pool = self.pool.get('industria.job')

        company_proxy = self.pool.get('res.company')._get_company_browse(
            cr, uid, context=context)

        cl_type = company_proxy.cl_mrp_lavoration_id
        cl_type_id = cl_type.id if cl_type else False
        location_src_id = cl_type.default_location_src_id.id
        location_dest_id = cl_type.default_location_dest_id.id

        job_ids = job_pool.search(cr, uid, [
            ('picking_id', '=', False),
            ('unused', '=', False),

            ('created_at', '!=', False),
            ('ended_at', '!=', False),

            ('state', '=', 'COMPLETED'),

            ('program_id.product_id', '!=', False),  # With semi product
        ], context=context)
        daily_job = {}
        for job in job_pool.browse(cr, uid, job_ids, context=context):
            database = job.database_id
            origin = '%s [%s]' % (database.name, database.ip)
            if origin not in daily_job:
                daily_job[origin] = {}

            date = '%s 08:00:00' % job.created_at[:10]  # Always at 8 o'clock
            if date not in daily_job[origin]:
                daily_job[origin][date] = {}
            product = job.program_id.product_id
            if product not in daily_job[origin][date]:
                daily_job[origin][date][product] = [
                    0, 0, []]  # Total, duration, job
            daily_job[origin][date][product][0] += 1  # piece (1 every job?)
            daily_job[origin][date][product][1] += job.job_duration
            daily_job[origin][date][product][2].append(job.id)

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
                    move_data.update({
                        'picking_id': picking_id,
                        'product_id': product.id,
                        'product_uom_qty': qty,
                        'location_id': location_src_id,
                        'location_dest_id': location_dest_id,
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
                robot_pool.create(
                    cr, uid, data, context=context)
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

        # 2. MY SQL:
        # TODO create context from ID (partial run)
        job_pool = self.pool.get('industria.job')
        robot_pool = self.pool.get('industria.robot')
        program_pool = self.pool.get('industria.program')

        from_industria_ref = False

        database_id = ids[0]
        connection = self.mssql_connect(cr, uid, ids, context=context)
        cursor = connection.cursor()

        try:
            if from_industria_ref:
                query = "SELECT * FROM jobs WHERE id >= %s;" % \
                        from_industria_ref
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
            program_db[program.industria_ref] = program.id

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
            program_id = program_db.get(record['program_id'], False)
            source_id = robot_db.get(record['source_id'], False)
            if source_id and program_id not in update_program:
                update_program.append(program_id)

                # Assign robot to the program (every program own to the robot)
                program_pool.write(cr, uid, [program_id], {
                    'source_id': source_id,
                }, context=context)

            data = {
                'industria_ref': industria_ref,

                # TODO check correct format
                'created_at': sql_get_date(record['created_at']),
                'updated_at': sql_get_date(record['updated_at']),
                'ended_at': sql_get_date(record['ended_at']),

                'source_id': source_id,
                'program_id': program_id,
                'database_id': database_id,
                'state': record['state'],
            }

            job_ids = job_pool.search(cr, uid, [
                ('database_id', '=', database_id),
                ('industria_ref', '=', industria_ref),
            ], context=context)
            if job_ids:
                job_pool.write(
                    cr, uid, job_ids, data, context=context)
            else:
                job_pool.create(
                    cr, uid, data, context=context)
        return True

    def import_job_ftp(self, cr, uid, ids, context=None):
        """ Import Job from FTP folder
        """
        def get_date(date):
            """ Extract FTP date
            """
            date = date.strip()
            try:
                date_part = date.split('-')
                year_part = date_part[:3]
                hour_part = date_part[3].split(':')

                date = '%04d-%02d-%02d %02d:%02d:%02d' % (
                    int(year_part[2]),
                    int(year_part[1]),
                    int(year_part[0]),

                    int(hour_part[0]),
                    int(hour_part[1]),
                    int(hour_part[2]),
                )
            except:
                _logger.error('Cannot convert in date: %s' % date)
                date = False
            return date

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
            _logger.error('Cannot extract file form robot via FTP')
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
        for line in open(fullname, 'r'):
            row = line.strip().split(';')
            if not line:
                continue

            if len(row) != 5:
                _logger.error('Wrong number of columns: %s' % line)
                continue

            program_name = row[0]
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
            }
            if job_ids:
                job_pool.write(cr, uid, job_ids, data, context=context)
            else:
                job_pool.create(cr, uid, data, context=context)

        _logger.info('Read file, moved in %s' % history_fullname)
        shutil.move(fullname, history_fullname)
        return True

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'partner_id': fields.many2one(
            'res.partner', 'Supplier'),
        'ip': fields.char('IP address', size=15),
        'username': fields.char('Username', size=64),
        'password': fields.char('Password', size=64),
        'database': fields.char('Database', size=64),
        'port': fields.integer('Port'),
        'note': fields.text('Note'),
        'ftp_command': fields.text(
            'FTP command', help='FTP command for unload Job'),
        'ftp_fullname': fields.char(
            'FTP fullname', size=180, help='Fullname for file with log'),
        'mode': fields.selection([
            ('mysql', 'My SQL'),
            ('mssql', 'MS SQL'),
            ('ftp', 'FTP'),
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
        'industria_ref': fields.integer('Industria ref key'),
        'database_id': fields.many2one(
            'industria.database', 'Database'),
        'partner_id': fields.related(
            'database_id', 'partner_id',
            type='many2one', relation='res.partner',
            string='Supplier', store=True),
        'note': fields.text('Note'),
        'today_state': fields.function(
            get_today_state, 'Status', type='text', method=True),
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
        'source_id': fields.many2one(
            'industria.robot', 'Robot'),
        'database_id': fields.many2one(
            'industria.database', 'Database'),
        'product_id': fields.many2one(
            'product.product', 'Semi product'),
        'partner_id': fields.related(
            'source_id', 'partner_id',
            type='many2one', relation='res.partner',
            string='Supplier', store=True),
        'note': fields.text('Note'),
        'medium': fields.float(
            'Media',
            help='Media calcolata giornalmente sui lavori di questo '
                 'programma'),
        'over_alarm': fields.float(
            'Allarme', help='Tempo per considerare il programma fuori media'),
    }


class IndustriaJob(orm.Model):
    """ Model name: Industria Job
        Field name keep as in MySQL for fast import
    """

    _name = 'industria.job'
    _description = 'Jobs'
    _rec_name = 'created_at'
    _order = 'created_at desc'

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
        # TODO remove?
        'dismiss': fields.boolean(
            'Job non completo', help='Job not completed or error'),
        'unused': fields.boolean(
            'Non usato per il magazzino',
            help='Job unused for stock movement, will not be linked '
                 'to picking'),
        'created_at': fields.datetime('Start'),
        'ended_at': fields.datetime('End'),
        'updated_at': fields.datetime('Modify'),
        # TODO duration seconds?

        'industria_ref': fields.integer('Industria ref key'),

        'program_id': fields.many2one(
            'industria.program', 'Program'),
        'database_id': fields.many2one(
            'industria.database', 'Database'),
        'source_id': fields.many2one(
            'industria.robot', 'Source Robot'),
        'partner_id': fields.related(
            'source_id', 'partner_id',
            type='many2one', relation='res.partner',
            string='Supplier', store=True),
        'state': fields.selection([
            ('ERROR', 'Error'),
            ('RUNNING', 'Running'),
            ('COMPLETED', 'Completed'),
            ], 'State', required=True),
        'notes': fields.text('Note'),
        'job_duration': fields.function(
            _get_duration, method=True,
            type='float', string='Duration',
            store={
                'industria.job': (
                    lambda self, cr, uid, ids, ctx=None: ids,
                    ['create_at', 'ended_at'],
                    10,
                )}),
        'picking_id': fields.many2one(
            'stock.picking', 'Picking',
            help='When generate a picking for stock movement will be linked '
                 'here'),
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
            'industria.program', 'source_id', 'Program'),
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
