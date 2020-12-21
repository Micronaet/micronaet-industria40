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
    def _load_alarms(self):
        """ Load alarms from file parameters
        """
        self._alarms = {}
        with io.open(
                self._alarms_file, encoding='utf-8', errors='ignore') as f:
            i = 0
            for line in f:
                i += 1
                row = line.strip().split('|')
                if not line or len(row) != 4:
                    print('%s. Load alarm error for this line' % i)
                self._alarms[row[0]] = row[1:]
                # alarm name, alarm description, alarm solution
        print('Loaded alarm files: %s' % self._alarms_file)

    class RobotConnectionError(Exception):
        print(u'Cannot connect with robot')

    # -------------------------------------------------------------------------
    # Check information:
    # -------------------------------------------------------------------------
    def alert_alarm_on_telegram(self, seconds=45, verbose_every=3600):
        """ Check all alarms and send in telegram
        """
        try:
            # Telegram:
            bot = telepot.Bot(self._telegram_token)
            bot.getMe()
            bot.sendMessage(
                self._telegram_group,
                u'[INFO] Inizio controllo allarmi su robot: %s' %
                self._robot_name)
            counter = 0
            error_found = []
            while True:
                counter += 1

                # Check running robot:
                plc_version = self.get_data_value(
                    self._node_command['version_check'])
                if plc_version:
                    print('PCL version: %s' % plc_version)
                else:
                    print('PCL version not found, robot not work [%s]' %
                          plc_version)
                    return False

                # Check N alarms in file:
                pdb.set_trace()
                for alarm in self._alarms.keys():
                    if self.get_data_value(
                            str(self._node_command['alarm_mask'] % alarm)):
                        if alarm in error_found:
                            print('[WARN] Yet raised: %s' % alarm)
                            continue

                        message_data = [self._robot_name]
                        message_data.extend(self._alarms[alarm])
                        event_text = u'[ALARM] Robot: %s\n' \
                                     u'Allarme: %s\n' \
                                     u'Problema: %s\n' \
                                     u'Soluzione: %s' % tuple(message_data)
                        try:
                            bot.sendMessage(self._telegram_group, event_text)
                            # Notified once:
                            if alarm not in error_found:
                                error_found.append(alarm)
                        except:
                            bot.sendMessage(
                                self._telegram_group, u'Error sending message')

                    else:  # No alarm remove from list:
                        if alarm in error_found:
                            message_data = [self._robot_name]
                            message_data.extend(self._alarms[alarm])
                            event_text = u'[RESUME] Robot: %s\n' \
                                         u'Allarme rientrato: %s' % tuple(
                                             message_data[:2])
                            try:
                                bot.sendMessage(
                                    self._telegram_group, event_text)
                                error_found.remove(alarm)  # Resume error
                            except:
                                bot.sendMessage(
                                    self._telegram_group,
                                    u'Error sending message')

                print(u'Check # %s' % counter)
                time.sleep(seconds)
                if verbose_every and counter % verbose_every == 0:
                    bot.sendMessage(
                        self._telegram_group,
                        u'[INFO] Robot %s working check # %s' % (
                            self._robot_name, counter))
                else:
                    print(u'Check # %s' % counter)
        except:
            print('Master error on alarm check: %s' % (sys.exc_info(), ))
            return False
        return True

    def get_data_value(self, node_description, comment='', verbose=True):
        """ Extract node data
        """
        node = self._client.get_node(node_description)
        try:
            data = node.get_data_value().Value._value
        except:
            raise ValueError('Cannot read, robot unplugged?')
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
        data = u''
        data += str(self.get_data_value(node_description, comment, verbose))

        # Check 200 alarms:
        for alarm in range(201):
            res = str(self.get_data_value(
                u'ns=6;s=::AsGlobalPV:Allarmi.N[%s].Dati.Attivo' % alarm,
                u'%s: N: %s' % (comment, alarm), verbose))

            if res:
                data += res
        return data

    def check_is_working(
            self,
            node_description="ns=6;s=::AsGlobalPV:PezzoPLC_InLavoro."
                             "CaricaInLavoroOK",
            comment='', verbose=True):
        """ Check master alarm status:
        """
        return str(
            self.get_data_value(node_description, u'Is working', verbose))

    def check_machine(self, comment='Macchina', verbose=True):
        """ Check some parameters:
        """
        data = u''
        data += str(self.get_data_value(
            "ns=6;s=::AsGlobalPV:AttrezzaturaInLavoro.Nome",
            u'%s: Attrezzatura in lavoro' % comment, verbose))
        # data += str(self.get_data_value(
        #     "ns=6;s=::AsGlobalPV:OreLavoroUtenza.N[1]",
        #     u'%s: Ore lavoro' % comment, verbose))

        data += str(self.get_data_value(
            "ns=6;s=::AsGlobalPV:Macchina.Stato",
            u'%s: Stato' % comment, verbose))
        data += str(self.get_data_value(
            "ns=6;s=::AsGlobalPV:Macchina.Manuale",
            u'%s: Manuale' % comment, verbose))
        data += str(self.get_data_value(
            "ns=6;s=::AsGlobalPV:Macchina.Automatico",
            u'%s: Automatico' % comment, verbose))
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

        space = u'  u' * level
        try:  # Used for leaf values:
            print(space, u'===> Data:', node_name, node.get_value())
            data_value = node.get_data_value()
            for detail in data_value.ua_types:
                detail_name = detail[0]
                print(
                    space,
                    u'    ---> Detail:',
                    detail_name,
                    data_value.__getattribute__(detail_name),
                    )
        except:  # Used for tree branch:
            print(space, u'::> Structure', node)
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
        self._telegram_token = config.get(u'Telegram', u'token')
        self._telegram_group = config.get(u'Telegram', u'group')

        # B. Command
        self._node_command = {
            'alarm_mask':  config.get(u'command', u'alarm_mask'),
            'version_check': config.get(u'command', u'version_check'),
        }

        # C. Alarms
        self._alarms_file = config.get(u'alarm', u'file')
        self._load_alarms()

        # D. Robot:
        self._robot_name = config.get(u'robot', u'name')
        self._robot_address = config.get(u'robot', u'address')
        print(u'Read config file %s for Robot: %s' % (
            self._robot_name, self._config_file))

        try:
            self._robot_port = config.get(u'robot', u'port')
        except:
            self._robot_port = 4840

        self._uri = u'opc.tcp://%s:%s' % (
            self._robot_address, self._robot_port)

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
