#!/usr/bin/python
# -*- coding: utf-8 -*-

from opcua_robot import RobotOPCUA

robot = RobotOPCUA()

print(robot.check_is_alarm())
print(robot.check_is_working())
print(robot.check_machine())

"""
::AsGlobalPV:Allarmi.N[x].Dati.Attivo            (BOOL)
::AsGlobalPV:AttrezzaturaInLavoro.Nome           (STRING[79])
::AsGlobalPV:Macchina.Stato                      (INTEGER)
::AsGlobalPV:Macchina.Manuale                    (BOOL)
::AsGlobalPV:Macchina.Automatico                 (BOOL)
::AsGlobalPV:OreLavoroUtenza.N[x]                (INTEGER)
"""
