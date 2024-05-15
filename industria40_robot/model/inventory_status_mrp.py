# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import pdb
import sys
import logging
import openerp
import xlsxwriter  # XLSX export
import pickle
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


class MrpProduction(orm.Model):
    """ Model name: MRP Production
    """

    _inherit = 'mrp.production'

    def schedule_unload_mrp_material_erpeek(self, cr, uid, context=None):
        """ Erpeek call for extract MRP unload data:
            1. for Tcar Tscar detail from MRP
            2. for movement and statistics

            Context dict:
            {'run_force': {
                'from_date': from_date,
                'to_date': to_date,
                'filename': filename,
                'update': False,  # Only dry run!
                }}
        """
        if context is None:
            context = {}

        return self.schedule_unload_mrp_material(
            cr, uid,
            from_date=context.get('run_force', {}).get('from_date'),
            context=context)

    # -------------------------------------------------------------------------
    # Override original function for link unload to Industria MRP:
    # -------------------------------------------------------------------------
    def schedule_unload_mrp_material(
            self, cr, uid, from_date=False,
            # filename=False,
            context=None):
        """ Update product field with unloaded elements
            Add also unload move to MRP status
            Context param: run_force used to force parameter in a dry run

            todo add parameter:
            only_mrp: force only MRP status not product

            Current load on file:
            filename
                /home/administrator/photo/log/mrp_unload_i40.xlsx
        """
        if context is None:
            context = {}

        # ---------------------------------------------------------------------
        # Utility function:
        # ---------------------------------------------------------------------
        def write_xls_log(log):
            """ Write log in WS updating counter
            """
            col = 0
            for item in log:
                self.ws.write(self.counter, col, item)
                col += 1
            self.counter += 1
            return

        # Pool used:
        product_pool = self.pool.get('product.product')
        unload_pool = self.pool.get('industria.mrp.unload')

        # ---------------------------------------------------------------------
        # Force procedure:
        # ---------------------------------------------------------------------
        run_force = context.get('run_force', {})
        # Force run parameters:
        from_date = run_force.get('from_date', from_date)
        to_date = run_force.get('to_date', False)
        update_mode = run_force.get('update', True)
        filename = run_force.get(
            'filename',
            '/home/administrator/photo/log/mrp_unload_i40.xlsx',  # Default
            )

        # todo use one year data instead?
        if not from_date:
            _logger.error('Pass from date to the procedure!!!')
            return False
        _logger.info('Start inventory MRP used from %s' % from_date)

        # ---------------------------------------------------------------------
        # XLS log export:
        # ---------------------------------------------------------------------
        if filename:
            _logger.warning('Log on file: %s' % filename)
            wb = xlsxwriter.Workbook(filename)
            self.ws = wb.add_worksheet('Unload')  # Work Sheet:
            self.counter = 0  # Row counters:
            # Write header
            write_xls_log([
                'MRP', 'Date',  'Order',
                'Product', 'Maked', 'ID',
                'Component', 'Maked', 'State',
                ])
        else:
            _logger.warning('No log on on file')

        # After inventory date:
        # todo get_range_inventory_date(self, cr, uid, context=None)

        domain = [
            # State filter (not needed):
            # ('state', 'not in', ('done', 'cancel')),
            ('date_planned', '>=', from_date),
            ]
        if to_date:
            domain.append(
                ('date_planned', '<=', to_date),
                )
        _logger.warning('Filter from %s to %s [%s mode]' % (
            from_date, to_date, 'update' if update_mode else 'no update',
            ))

        mrp_ids = self.search(cr, uid, domain, context=context)

        # ---------------------------------------------------------------------
        # Clean operation:
        # ---------------------------------------------------------------------
        if update_mode:
            # Current assign in product:
            cr.execute('UPDATE product_product set mx_mrp_out=0;')
            # Current I40 load:
            cr.execute('DELETE FROM industria_mrp_unload;')

        # ---------------------------------------------------------------------
        # A. Setup unload starting with SOL error:
        # ---------------------------------------------------------------------
        pdb.set_trace()
        mrp_unload = {}
        product_unload = {}

        cr.execute('''
            SELECT product_id, sum(error_qty) 
            FROM sale_order_line_error 
            WHERE date >= '%s' 
            GROUP BY product_id 
            HAVING sum(error_qty) > 0;
            ''' % from_date)

        for record in cr.fetchall():
            product_id = record[0]
            maked = record[0]

            product = product_pool.browse(cr, uid, product_id, context=context)
            for item in product.dynamic_bom_line_ids:
                component = item.product_id
                product_id = component.id
                cmpt_maked = maked * item.product_qty
                if product.id in product_unload:
                    product_unload[product_id] += cmpt_maked
                else:
                    product_unload[product_id] = cmpt_maked

        # ---------------------------------------------------------------------
        # B. Generate MRP total component report with totals:
        # ---------------------------------------------------------------------
        for mrp in self.browse(cr, uid, mrp_ids, context=context):
            # Collect fabric semiproduct (if needed):
            industria_mrp = mrp.industria_mrp_id
            if industria_mrp:
                _logger.info('Fount I4.0 MRP %s' % mrp.name)
                fabric_semiproduct = [
                    item.product_id.id for item in industria_mrp.line_ids]
                industria_mrp_id = industria_mrp.id
            else:
                _logger.info('No I4.0 MRP %s' % mrp.name)
                fabric_semiproduct = []
                industria_mrp_id = False  # Not used

            for sol in mrp.order_line_ids:
                # Total elements:
                maked = sol.product_uom_maked_sync_qty
                if not maked:
                    continue
                for component in sol.product_id.dynamic_bom_line_ids:
                    product = component.product_id
                    product_id = product.id
                    _logger.info('SL: %s' % product.name)

                    cmpt_maked = maked * component.product_qty
                    if product.id in product_unload:
                        product_unload[product_id] += cmpt_maked
                    else:
                        product_unload[product_id] = cmpt_maked
                    if industria_mrp and product_id in fabric_semiproduct:
                        if product_id in mrp_unload:
                            mrp_unload[(industria_mrp_id, product_id)] += maked
                        else:
                            mrp_unload[(industria_mrp_id, product_id)] = maked

                    if filename:
                        write_xls_log([
                            mrp.name, mrp.date_planned, sol.order_id.name,
                            # Product
                            sol.product_id.default_code, maked,
                            # Component
                            product_id, product.default_code, cmpt_maked,
                            mrp.state,
                            ])

        if filename:
            wb.close()

        if update_mode:
            # Update MRP I4.0
            for key in mrp_unload:
                industria_mrp_id, product_id = key
                unload_pool.create(cr, uid, {
                    'industria_mrp_id': industria_mrp_id,
                    'product_id': product_id,
                    'quantity': mrp_unload[key],
                }, context=context)

            # Update product status:
            for product_id, unload in product_unload.iteritems():
                product_pool.write(cr, uid, product_id, {
                    'mx_mrp_out': unload,
                    }, context=context)
        else:  # Dry run mode:
            product_unload_text = pickle.dumps(product_unload)
            return product_unload_text  # Converted in Text
