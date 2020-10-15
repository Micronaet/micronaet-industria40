#!/usr/bin/python
# -*- coding: utf-8 -*-

import pdb
import time
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
        print('Cannot connect with robot')

    # -------------------------------------------------------------------------
    # Check information:
    # -------------------------------------------------------------------------
    def alert_alarm_on_telegram(self, seconds=60, verbose_every=3600):
        """ Check all alarms and send in telegram
        """
        # Telegram:
        bot = telepot.Bot(self._telegram_token)
        bot.getMe()

        counter = 0
        while True:
            counter += 1

            # Check 200 alarms:
            alarm_list = []
            for alarm in range(201):
                if self.get_data_value(
                        'ns=6;s=::AsGlobalPV:Allarmi.N[%s].Dati.Attivo' %
                        alarm):
                    alarm_list.append(str(alarm))

            if alarm_list:
                event_text = '[ALARM] Robot: %s Alarm present:\n%s' % (
                    self._robot_name,
                    ','.join(alarm_list)
                )
                try:
                    bot.sendMessage(self._telegram_group, event_text)
                except:
                    bot.sendMessage(
                        self._telegram_group, 'Error sending message')
            print('Check # %s' % counter)
            time.sleep(seconds)
            if counter % verbose_every == 0:
                bot.sendMessage(
                    self._telegram_group,
                    '[INFO] Robot %s working check # %s' % (
                        self._robot_name, counter))
            else:
                print('Check # %s' % counter)
            # Check master alarm:
            """
            alarm_status = str(self.get_data_value(
                'ns=6;s=::AsGlobalPV:Allarmi.Presente',
            ))
            if alarm_status:
                event_text = 'Robot: %s Mater Alarm present\n%s' % (
                    self._robot_name,
                    ','.join(alarm_list)
                )
                bot.sendMessage(self._telegram_group, event_text)
            """
            # Check all 200 alarms:
            """
            for alarm in range(201):
                alarm_status = str(self.get_data_value(
                    'ns=6;s=::AsGlobalPV:Allarmi.N[%s].Dati.Attivo' % alarm,
                ))
                if alarm_status:
                    event_text = 'Robot: %s Alarm present: # %s' % (
                        self._robot_name, alarm,
                    )
                    bot.sendMessage(self._telegram_group, event_text)
            """
        return True

    def get_data_value(self, node_description, comment='', verbose=True):
        """ Extract node data
        """
        node = self._client.get_node(node_description)
        try:
            data = node.get_data_value().Value._value
        except:
            data = '[ERR] Node access error (not readable!)'
        if verbose:
            comment = comment or node_description
            print(comment, data)
        return data

    def check_is_alarm(
            self,
            node_description="ns=6;s=::AsGlobalPV:Allarmi.Presente",
            comment='Is alarm', verbose=True):
        """ Check master alarm status:
        """
        data = ''
        data += str(self.get_data_value(node_description, comment, verbose))

        # Check 200 alarms:
        for alarm in range(201):
            data += str(self.get_data_value(
                'ns=6;s=::AsGlobalPV:Allarmi.N[%s].Dati.Attivo' % alarm,
                '%s: N: %s' % (comment, alarm), verbose))

        return data

    def check_is_working(
            self,
            node_description="ns=6;s=::AsGlobalPV:PezzoPLC_InLavoro."
                             "CaricaInLavoroOK",
            comment='', verbose=True):
        """ Check master alarm status:
        """
        return str(
            self.get_data_value(node_description, 'Is working', verbose))

    def check_machine(self, comment='Macchina', verbose=True):
        """ Check some parameters:
        """
        data = ''
        data += str(self.get_data_value(
            "ns=6;s=::AsGlobalPV:AttrezzaturaInLavoro.Nome",
            '%s: Attrezzatura in lavoro' % comment, verbose))
        # data += str(self.get_data_value(
        #     "ns=6;s=::AsGlobalPV:OreLavoroUtenza.N[1]",
        #     '%s: Ore lavoro' % comment, verbose))

        data += str(self.get_data_value(
            "ns=6;s=::AsGlobalPV:Macchina.Stato",
            '%s: Stato' % comment, verbose))
        data += str(self.get_data_value(
            "ns=6;s=::AsGlobalPV:Macchina.Manuale",
            '%s: Manuale' % comment, verbose))
        data += str(self.get_data_value(
            "ns=6;s=::AsGlobalPV:Macchina.Automatico",
            '%s: Automatico' % comment, verbose))
        return data

    # -------------------------------------------------------------------------
    # Tree inspect
    # -------------------------------------------------------------------------
    def print_node(self, node_name='', level=0):
        """ Inspect node tree branch
        """
        if node_name:
            node = self._client.get_root_node(node_name)
        else:
            # Use root node:
            node = self._client.get_root_node()

        space = '  ' * level
        try:  # Used for leaf values:
            print(space, '===> Data:', node_name, node.get_value())
            data_value = node.get_data_value()
            for detail in data_value.ua_types:
                detail_name = detail[0]
                print(
                    space,
                    '    ---> Detail:',
                    detail_name,
                    data_value.__getattribute__(detail_name),
                    )
        except:  # Used for tree branch:
            print(space, '::> Structure', node)
            for child_node in node.get_children():
                self.print_node(child_node, level=level+1)

    def __init__(self, config_file='./start.cfg'):
        """ Constructor for create object
        """
        # ---------------------------------------------------------------------
        # File parameters:
        # ---------------------------------------------------------------------
        # Open config file:
        self._config_file = config_file
        config = ConfigParser.ConfigParser()
        config.read([self._config_file])

        # A. Telegram:
        self._telegram_token = config.get('Telegram', 'token')
        self._telegram_group = config.get('Telegram', 'group')

        # B. Robot:
        self._robot_name = config.get('robot', 'name')
        self._robot_address = config.get('robot', 'address')
        print('Read config file %s for Robot: %s' % (
            self._robot_name,
            self._config_file,
        ))

        try:
            self._robot_port = config.get('robot', 'port')
        except:
            self._robot_port = 4840

        self._uri = 'opc.tcp://%s:%s' % (self._robot_address, self._robot_port)

        # Create and connect as client:
        self._client = Client(self._uri)
        try:
            self._client.connect()
        except:
            raise self.RobotConnectionError(self)

    def __del__(self):
        """ Destructor for clean connection when garbage object
        """
        print('Disconnect from robot')
        try:
            self._client.disconnect()
        except:
            print('Error disconnecting from Robot: %s' % self._name)
