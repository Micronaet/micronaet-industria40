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

        bot.sendMessage(
            self._telegram_group,
            '[INFO] Start check alarm robot: %s' % self._robot_name)
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
                message_data = [self._robot_name]
                message_data.extend(self.get_data_value(alarm))
                event_text = '[ALARM] Robot: %s\n' \
                             'Allarme: %s\n' \
                             'Problema: %s\n' \
                             'Soluzione: %s' % tuple(message_data)
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
            """
            # Check master alarm:
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

    def get_alarm_info(self, number):
        """ Get alarm info by code
        """
        alarms = {
            1: ['Emergenza Fungo', 'Fungo di Emergenza premuto',
                'Sbloccare fungo di emergenza e premere pulsante marcia'],
            2: ['Termico', 'Termica Motori',
                'Verificare la termica motori nel quadro elettrico'],
            3: ['Termostato', 'Temperatura Olio superiore al valore impostato',
                'Attendere raffreddamento o verificare il corretto '
                'funzionamento dello scambiatore'],
            4: ['Pressostato', 'Pressione aria inferiore al valore settato',
                'Verificare pressione dell’aria'],
            7: ['Errore CNC',
                'Errore generico durante l’esecuzione in automatico',
                'Verificare quote assi e/o velicità'],
            8: ['Assi non abilitati', 'Assi non in ready',
                'Verificare fusibili potenza o eventuali errori su driver led '
                'rosso'],
            11: ['Livello Olio',
                 'Livello dell’Olio sotto il minimo consentito',
                 'Reboccare Olio'],
            12: ['Filtro Olio', 'Filtro dell’Olio intasato',
                 'Togliere il Filtro e pulirlo con aria compressa'],
            17: ['Misura Canotto Modificata',
                 'Impostato un valore di misura canotto diversa dalla '
                 'precedentemente trasferita',
                 'Ripetere azzeramento macchina'],
            18: ['Misura Quota Massima Modificata',
                 'Impostato un valore di lunghezza macchina diverso da quello '
                 'impostato precedentemente',
                 'Trasferire Utensile e ripetere azzeramento macchina'],
            101: ['Timeout Matrice Avanti',
                  'Mancata verifica sul sensore di matrice avanti',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            102: ['Timeout Morsa Chiusa',
                  'Mancata verifica sul sensore di morsa chiusa',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            103: ['Timeout Carro Chiuso',
                  'Mancata verifica sul sensore di carro chiuso',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            104: ['Timeout Pinza Chiusa',
                  'Mancata verifica sul sensore di pinza chiusa',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            105: ['Timeout Anima Avanti',
                  'Mancata verifica sul sensore di anima avanti',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            106: ['Timeout Slitta Avanti',
                  'Mancata verifica sul sensore di slitta avanti',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            107: ['Timeout Cambio Piano ',
                  'Mancata verifica sul sensore di piano 2',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            114: ['Timeout Battuta Avanti',
                  'Mancata verifica sul sensore di battuta avanti',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            121: ['Timeout Matrice Indietro',
                  'Mancata verifica sul sensore di matrice indietro',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            122: ['Timeout Morsa Aperta',
                  'Mancata verifica sul sensore di morsa aperta',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            123: ['Timeout Carro Aperto',
                  'Mancata verifica sul sensore di carro aperto',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            124: ['Timeout Pinza Aperta',
                  'Mancata verifica sul sensore di pinza aperta',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            125: ['Timeout Anima Indietro',
                  'Mancata verifica sul sensore di anima indietro',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            126: ['Timeout Slitta Indietro',
                  'Mancata verifica sul sensore di slitta indietro',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            127: ['Timeout Cambio Piano ',
                  'Mancata verifica sul sensore di piano 1',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            134: ['Timeout Battuta Indietro',
                  'Mancata verifica sul sensore di battuta avanti',
                  'Verificare la corretta segnalazione del sensore e/o del '
                  'movimento del cilindro'],
            150: ['Blocco comando Asse-X per INTERFERENZA con Matrice',
                  'Asse R non in posizione corretta',
                  'Selezionare Asse R e portarlo a raggio matrice'],
            151: ['Blocco inserimento Carro per INTERFERENZA con Asse X',
                  'Asse X in zona di interferenza, non è possibile chiudere '
                  'il carro',
                  'Selezionare Asse X e portalo fuori dalla zona di '
                  'interferenza '],
            152: ['Blocco discesa piano per INTERFERENZA',
                  'Asse X in zona di interferenza, non è possibile cambiare '
                  'piano',
                  'Selezionare Asse X e portalo fuori dalla zona di '
                  'interferenza'],
            153: ['Blocco salita piano per INTERFERENZA',
                  'Asse X in zona di interferenza, non è possibile cambiare '
                  'piano',
                  'Selezionare Asse X e portalo fuori dalla zona di '
                  'interferenza'],
            154: ['Blocco comando Asse-X per strappo tubo. APRIRE Morsa/Carro '
                  'e/o la Pinza',
                  'Non è possibile muovere Asse X per condizioni elencate',
                  'Verificare sensore morsa/carro/pinza aperti o posizionare '
                  'morsa/carro/pinza aperti'],
            155: ['Blocco comando Asse-Y per strappo tubo. APRIRE Morsa/Carro '
                  'e/o la Pinza',
                  'Non è possibile muovere Asse Y per condizioni elencate',
                  'Verificare sensore morsa/carro/pinza aperti o posizionare '
                  'morsa/carro/pinza aperti'],
            156: ['Blocco inserimento Carro per INTERFERENZA con Asse R',
                  'Non è possibile chiudere il carro per Asse R non a raggio '
                  'matrice',
                  'Selezionare Asse R e portarlo a raggio matrice'],
            157: ['Blocco comando Asse-R per carro NON aperto',
                  'Non è possibile muovere Asse R per carro chiuso',
                  'Verificare sensore carro aperto o posizionare carro '
                  'aperto'],
            158: ['Blocco comando Asse-R Indietro',
                  'Non è possibile muovere Asse R indietro perchè raggiunto '
                  'limite matrice', ''],
            159: ['Blocco avanti slitta Asse-Y INFERIORE 91°',
                  'Non è possibile muovere slitta avanti perchè in '
                  'interferenza con asse Y',
                  u'Selezionare Asse Y e portarlo a una quota superiore di '
                  '91°'],
            160: ['Blocco comando Asse-Y per Slitta NON indietro',
                  'Non è possibile muovere Asse Y indietro perchè slitta non '
                  'in posizione indietro',
                  'Verificare sensore slitta indietro o posizionare slitta '
                  'indietro'],
            161: ['Blocco inserimento Morsa per Asse-Y NON a 0°',
                  'Non è possibile chiudere morsa perchè Asse Y non a zero',
                  'Selezionare Asse Y e portarlo a una quota 0'],
            164: ['Blocco comando Asse-X per Piano Attuale UGUALE a 0',
                  'Non è possibile muovere Asse X perchè il piano non è '
                  'selezionato',
                  'Verificare sensore piano attuale o cambiare piano 1 – 2'],
            165: ['Blocco inserimento Morsa per Matrice NON indietro',
                  'Non è possibile chiudere morsa perchè matrice non in '
                  'posizione indietro',
                  'Verificare sensore matrice indietro o posizionare matrice '
                  'indietro'],
            167: ['Blocco comando inserimento Carro per Slitta NON indietro',
                  'Non è possibile chiudere carro perchè slitta non in '
                  'posizione indietro',
                  'Verificare sensore slitta indietro o posizionare slitta '
                  'indietro'],
            168: ['Blocco comando Asse-R per morsa NON aperta',
                  'Non è possibile muovere Asse R per morsa chiusa',
                  'Verificare sensore morsa aperta o posizionare morsa '
                  'aperta'],
            169: ['Blocco Inserimento Morsa INTERFERENZA con Asse R',
                  'Non è possibile chiudere morsa per Asse R non a raggio '
                  'matrice',
                  'Selezionare Asse R e portarlo a raggio matrice'],
            171: ['Allarme Keyence', 'Modulo di sicurezza Keyence in errore',
                  'Verificare il corretto funzionamento del modulo tramite il '
                  'software installato sul PC'],
            172: ['ALLARME - Blocco Asse Z per Battuta Giu',
                  'Non è possibile muovere Asse Z per battuta giu',
                  'Verificare sensore battuta su o posizionare battuta su'],
            173: ['ALLARME - Blocco Battuta per Asse Z > 0',
                  'Non è possibile muovere Battuta per Asse Z non a 0',
                  'Selezionare Asse Z e portarlo a 0'],
            }
        if number in alarms:
            return alarms[number]
        else:
            return ['Allarme generico #%s' % number, '/', '/']
