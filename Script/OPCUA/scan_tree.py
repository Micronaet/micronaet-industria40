#!/usr/bin/python
# -*- coding: utf-8 -*-

from opcua_robot import RobotOPCUA

robot = RobotOPCUA()

# -----------------------------------------------------------------------------
# Some start:
# -----------------------------------------------------------------------------
# Master:
robot.scan_node()

# Some example.
global_node_name = "ns=6;s=::AsGlobalPV"
robot.scan_node(global_node_name)

working_node_name = "ns=6;s=::AsGlobalPV:AttrezzaturaInLavoro"
robot.scan_node(working_node_name)

piece_working_node_name = "ns=6;s=::AsGlobalPV:PezzoPLC_InLavoro"
robot.scan_node(piece_working_node_name)

type_node_name = "ns=0;i=24"
robot.scan_node(type_node_name)

"""
node = client.get_node("ns=6;s=::AsGlobalPV:Allarmi.Codice")
print(node.get_node_class())
print(node.get_browse_name())
print(node.get_display_name())
print(node.get_description())
print(node.get_data_type())

node =  client.get_node("ns=6;s=::AsGlobalPV:Allarmi.Presente")
node =  client.get_node("ns=6;s=::AsGlobalPV:Allarmi.Contatore")
print(node.get_value())
"""

