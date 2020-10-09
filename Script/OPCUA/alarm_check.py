#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import pdb
from opcua import Client
import ConfigParser
from opcua_robot import RobotOPCUA

robot = RobotOPCUA()

print(robot.check_is_allarm())
print(robot.check_is_working())


# -----------------------------------------------------------------------------
# Browse node:
# -----------------------------------------------------------------------------
# Some start:
root_node = client.get_root_node()
global_node = client.get_node("ns=6;s=::AsGlobalPV")
working_node = client.get_node("ns=6;s=::AsGlobalPV:AttrezzaturaInLavoro")
piece_working_node = client.get_node("ns=6;s=::AsGlobalPV:PezzoPLC_InLavoro")
type_node = client.get_node("ns=0;i=24")

# Setup and browse:
start_node = piece_working_node  # TODO Changeme
print_node(start_node)
client.disconnect()
sys.exit()

node = client.get_node("ns=6;s=::AsGlobalPV:Allarmi.Codice")
print(node.get_node_class())
print(node.get_browse_name())
print(node.get_display_name())
print(node.get_description())
print(node.get_data_type())
pdb.set_trace()
client.disconnect()
sys.exit()


# node =  client.get_node("ns=6;s=::AsGlobalPV:Allarmi.Presente")
node =  client.get_node("ns=6;s=::AsGlobalPV:Allarmi.Contatore")
print(node.get_value())
pdb.set_trace()
node =  client.get_node("ns=6;s=::AsGlobalPV:Allarmi")

# node = client.get_node("ns=6;s=::AsGlobalPV:VersionePLC")
# print(node.get_value())
client.disconnect()
sys.exit()


