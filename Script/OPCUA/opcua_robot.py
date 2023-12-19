#!/usr/bin/python
# -*- coding: utf-8 -*-

import pdb
import sys
import time
import io
from opcua import Client
import telepot
try:
    import ConfigParser
except:
    import configparser as ConfigParser


class RobotOPCUA:
    """ Robot OPC UA Management
    """

    class RobotConnectionError(Exception):
        print(u'Cannot connect with robot')

    def get_data_value(self, node_description, comment='', verbose=True):
        """ Extract node data
        """
        node = self._client.get_node(node_description)
        try:
            data = node.get_data_value().Value._value
        except:
            raise ValueError(
                'Cannot read: %s, robot unplugged?' % node_description)
        if verbose:
            comment = comment or node_description
            print(comment, data)
        return data

        # ---------------------------------------------------------------------
        # File parameters:
        # ---------------------------------------------------------------------
        # Open config file:
        

        # Create and connect as client:
        self._client = Client(self._uri)
        try:
            self._client.connect()
        except:
            raise self.RobotConnectionError(self)

    def __del__(self):
        """ Destructor for clean connection when garbage object
        """
        print(u'Disconnect from robot')
        try:
            self._client.disconnect()
        except:
            try:
                name = self._name
            except:
                name = '[Non present]'
            print(u'Error disconnecting from Robot: %s' % name)

    def get_alarm_info(self, number):
        """ Get alarm info by code
        """
        if number in self._alarms:
            return self._alarms[number]
        else:
            return [u'Allarme generico #%s' % number, u'/', u'/']
