#!/usr/bin/python
# -*- coding: utf-8 -*-

from opcua_robot import RobotOPCUA

robot = RobotOPCUA()

print(robot.check_is_allarm())
print(robot.check_is_working())
