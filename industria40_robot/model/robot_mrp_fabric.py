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


class IndustriaMrp(orm.Model):
    """ Model name: Industria 4.0 MRP
    """

    _name = 'industria.mrp'
    _description = 'Industria 4.0 MRP'
    _order = 'date desc'
    _rec_name = 'date'

    _columns = {
        'date': fields.date(
            'Data', help='Data di creazione'),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('open', 'Aperto'),
            ('closed', 'Chiuso'),
            ('paused', 'In pausa'),
        ], 'Stato')
    }

    _defaults = {
        'state': lambda *x: 'draft',
    }


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
            'industria.mrp', 'Produzione I40',
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
    }
