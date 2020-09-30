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

_logger = logging.getLogger(__name__)


class IndustriaDatabase(orm.Model):
    """ Model name: Industria Database
    """

    _name = 'industria.database'
    _description = 'Database PC'
    _rec_name = 'name'
    _order = 'name'

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'ip': fields.char('IP address', size=15),
        'username': fields.char('Username', size=64, required=True),
        'password': fields.char('Password', size=64, required=True),
        'database': fields.char('Database', size=64, required=True),
        'port': fields.integer('Port', required=True),
        'note': fields.text('Note'),
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
        'partner_id': fields.many2one(
            'res.partner', 'Supplier', required=True),
        'database_id': fields.many2one(
            'industria.database', 'Database'),
        'mode': fields.selection([
            ('mysql', 'My SQL'),
            ('mssql', 'MS SQL'),
            ], 'Mode', required=True),
        'note': fields.text('Note'),
    }

    _defaults = {
        'mode': lambda *x: 'mysql',
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
