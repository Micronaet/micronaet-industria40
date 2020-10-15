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
import telepot
import ConfigParser
from opcua_robot import RobotOPCUA

# Load Robot:
robot = RobotOPCUA()
robot.alert_alarm_on_telegram()
# robot.check_is_alarm()
# robot.check_is_working()
# robot.check_machine()
del robot

"""
::AsGlobalPV:Allarmi.N[x].Dati.Attivo            (BOOL)
::AsGlobalPV:AttrezzaturaInLavoro.Nome           (STRING[79])
::AsGlobalPV:Macchina.Stato                      (INTEGER)
::AsGlobalPV:Macchina.Manuale                    (BOOL)
::AsGlobalPV:Macchina.Automatico                 (BOOL)
::AsGlobalPV:OreLavoroUtenza.N[x]                (INTEGER)
"""
