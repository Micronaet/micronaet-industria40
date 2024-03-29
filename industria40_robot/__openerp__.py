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

{
    'name': 'Industria 4.0 - Menu Robot',
    'version': '0.1',
    'category': 'Menu',
    'description': ''' 
        Menu Robot 1       
        ''',
    'author': 'Micronaet S.r.l. - Nicola Riolini',
    'website': 'http://www.micronaet.it',
    'license': 'AGPL-3',
    'depends': [
        'base',
        'industria40_base',
        'mrp',
        'stock',  # For SL Movement
        'production_accounting_external',
        'mx_close_order',
        'bom_dynamic_structured',
        'lavoration_cl_sl',  # For stock unload
        'inventory_status_mrp',   # Microntaet/micronaet-product for status
        ],
    'init_xml': [],
    'demo': [],
    'data': [
        'security/ir.model.access.csv',

        'views/robot_oven_view.xml',
        'views/industria_mrp_view.xml',

        'views/menu_view1.xml',
        'views/menu_view2.xml',
        'views/menu_view3.xml',
        'views/menu_view4.xml',
        'views/menu_view5.xml',

        'wizard/switch_stock_wizard_view.xml',
        # 'wizard/assign_stock_wizard_view.xml',
        ],
    'active': False,
    'installable': True,
    'auto_install': False,
    }
