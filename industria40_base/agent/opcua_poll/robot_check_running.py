 # -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
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
import erppeek
import ConfigParser
import sys
import opcua
from opcua import ua
import pdb


def get_robot(address, port):
    uri = u'opc.tcp://%s:%s' % (address, port)

    # Create and connect as client:
    robot = opcua.Client(uri)
    try:
        robot.connect()
        return robot
    except:
        return False


def get_data_value(robot, node_description, comment='', verbose=True):
    """ Extract node data
    """
    node = robot.get_node(node_description)
    try:
        data = node.get_data_value().Value._value
    except:
        print('Cannot read: %s, robot unplugged?' % node_description)
        return 'ERROR'
    if verbose:
        comment = comment or node_description
        print(comment, data)
    return data


def set_data_value(robot, node_description, value):
    """ Save node data
    """
    node = robot.get_node(node_description)
    try:
        node.set_value(
            ua.DataValue(ua.Variant(
                value,
                node.get_data_type_as_variant_type()
            )))
    except:
        print('Cannot read: %s, robot unplugged?\n%s' % (
            node_description,
            sys.exc_info(), ))
        return False
    return True


def host_up(host):
    if os.system('ping -c 2 %s' % host) is 0:
        return True
    else:
        return False

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
# todo Test OPCUA variables
# todo Update ODOO if done (add time, duration)
pdb.set_trace()
robot = get_robot('10.10.10.1', 4840)
calls = {
    'temp_grease': 'ns=3;s="DB_TERMOREG".NR[1].TEMPERATURA',
    'temp_dry': 'ns=3;s="DB_TERMOREG".NR[6].TEMPERATURA',
    'temp_bake': 'ns=3;s="DB_TERMOREG".NR[7].TEMPERATURA',
    'speed': 'ns=3;s="DB_TRAINO".ACT_VEL_TRAINO[1]',
    }


for call in calls:
    print('\nChiamata %s' % call)
    result = get_data_value(
        robot,
        call,
        verbose=False,
    )
    print('Risposta: %s' % result)
robot.disconnect()
