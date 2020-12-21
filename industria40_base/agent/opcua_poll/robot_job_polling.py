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
import opcua
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
        raise ValueError('Cannot read, robot unplugged?')
    if verbose:
        comment = comment or node_description
        print(comment, data)
    return data


def host_up(host):
    if os.system('ping -c 2 %s' % host) is 0:
        return True
    else:
        return False

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
"""cfg_file = os.path.expanduser('../openerp.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port),
    db=dbname,
    user=user,
    password=pwd,
    )

job_pool = odoo.model('industria.job')

job_ids = job_pool.search([
    ('database_id.mode', '=', 'opcua'),  # Only opcua database job
    ('state', '=', 'RUNNING'),  # Only running job
])
"""
# TODO Test OPCUA variables
# TODO Update ODOO if done (add time, duration)
robot = get_robot('10.10.10.1', 4840)
command = 'ns=3;s="DB_1_SCAMBIO_DATI_I4_0"."Colore"[0]'
print(get_data_value(robot, command))

