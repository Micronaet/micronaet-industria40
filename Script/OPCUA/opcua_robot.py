#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import pdb
from opcua import Client
import ConfigParser


class RobotOPCUA:
    """ Robot OPC UA Management
    """
    def __init__(self, name='Robot 1', config_file='./robot.cfg'):
        """ Constructor for create object
        """
        self._name = name
        self._config_file = config_file

        print('Read config file %s for Robot: %s' % (
            self._name,
            self._config_file,
        ))
        self._uri = self.get_uri()

        # Create and connect as client:
        self._client = Client(self._uri)
        self._client.connect()

    def __del__(self):
        """ Clean connection before destruct
        """
        print('Disconnect from robot')
        self._client.disconnect()

    @staticmethod
    def get_uri(self):
        """ Load parameter from config file
        """
        config = ConfigParser.ConfigParser()
        config.read([self._config_file])

        # File parameters:
        address = config.get('robot', 'address')
        try:
            port = config.get('robot', 'port')
        except:
            port = 4840

        return 'opc.tcp://%s:%s' % (address, port)

    @staticmethod
    def print_node(self, node, level=0):
        space = '  ' * level
        try:  # Used for leaf values:
            print(space, ' ---> Data:', node, node.get_value())
            data_value = node.get_data_value()
            for detail in data_value.ua_types:
                detail_name = detail[0]
                print(
                    space,
                    '      :::> Detail:',
                    detail_name,
                    data_value.__getattribute__(detail_name),
                    )
        except:  # Used for tree branch:
            print(space, ' ===> Structure', node)
            for child_node in node.get_children():
                self.print_node(child_node, level=level+1)

    def get_data_value(self, node_description, comment='', verbose=True):
        """ Extract node data
        """
        node = self._client.get_node(node_description)
        data = node.get_data_value().Value._value
        if verbose:
            comment = comment or node_description
            print(comment, data)
        return data

    def check_is_alarm(
            self,
            node_description="ns=6;s=::AsGlobalPV:Allarmi.Presente",
            comment='', verbose=True):
        """ Check master alarm status:
        """
        return self.get_data_value(node_description, 'Is alarm', verbose)

    def check_is_alarm(
            self,
            node_description="ns=6;s=::AsGlobalPV:PezzoPLC_InLavoro."
                             "CaricaInLavoroOK",
            comment='', verbose=True):
        """ Check master alarm status:
        """
        return self.get_data_value(node_description, 'Is working', verbose)
