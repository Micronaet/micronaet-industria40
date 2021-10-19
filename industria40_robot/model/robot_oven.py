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


class MrpProductionOven(orm.Model):
    """ Model name: MrpProductionOven
    """

    _inherit = 'mrp.production'

    def explode_oven_job_per_color(self, cr, uid, ids, context=None):
        """ Generate Oven job
        """
        explode = {}
        for mrp in self.browse(cr, uid, ids, context=context):
            for line in mrp.order_line_ids:
                default_code = line.product_id.default_code
                parent_code = default_code[:3].strip()
                color_code = default_code[6:8].strip()
                if not color_code:
                    continue  # neutral color
                if color_code not in explode:
                    explode[color_code] = {}
                if parent_code not in explode[color_code]:
                    explode[color_code][parent_code] = 0

                # Get remain:
                remain_mrp = (
                        line.product_uom_qty - line.mx_assigned_qty -
                        line.product_uom_maked_sync_qty)
                remain_delivery = line.product_uom_qty - line.delivered_qty
                if remain_delivery > remain_mrp:  # Use minor
                    remain = remain_mrp
                else:
                    remain = remain_delivery
                explode[color_code][parent_code] += remain

        # Generate wizard procedure:

        return True

    _columns = {
        'industria_oven_pending': fields.boolean(
            'Da verniciare',
            help='Marcare la produzione per essere verniciata'),
    }


class MrpProductionOvenSelected(orm.Model):
    """ Wizard name: class Mrp Production Oven Selected
    """

    _name = 'mrp.production.oven.selected'
    _description = 'Pre selection wizard'
    _order = 'parent_code, color_code'
    _rec_name = 'parent_code'

    def generate_oven_job(self, cr, uid, ids, context=None):
        """ Generate Oven job
        """

        return True

    _columns = {
        'send': fields.boolean('Da spedire'),
        'parent_code': fields.char(
            'Codice padre', size=5, required=True),
        'color_code': fields.char(
            'Codice colore', size=5, required=True),
        'total': fields.integer('Totali'),
        'partial': fields.integer(
            'Parziali', help='Pezzi parziali da mandare in lavorazione'),
        'from_date': fields.date('Dalla data'),
        'to_date': fields.date('Alla data'),
        'mrp_ids': fields.many2many(
            'mrp.production', 'i40_oven_mrp_rel',
            'wizard_id', 'mrp_id',
            'Produzioni'),
    }
