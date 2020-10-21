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
    _alarms = {
        1: [u'Emergenza Fungo', u'Fungo di Emergenza premuto',
            u'Sbloccare fungo di emergenza e premere pulsante marcia'],
        2: [u'Termico', u'Termica Motori',
            u'Verificare la termica motori nel quadro elettrico'],
        3: [u'Termostato',
            u'Temperatura Olio superiore al valore impostato',
            u'Attendere raffreddamento o verificare il corretto '
            u'funzionamento dello scambiatore'],
        4: [u'Pressostato', u'Pressione aria inferiore al valore settato',
            u'Verificare pressione dell’aria'],
        7: [u'Errore CNC',
            u'Errore generico durante l’esecuzione in automatico',
            u'Verificare quote assi e/o velicità'],
        8: [u'Assi non abilitati', u'Assi non in ready',
            u'Verificare fusibili potenza o eventuali errori su driver led'
            u' rosso'],
        11: [u'Livello Olio',
             u'Livello dell’Olio sotto il minimo consentito',
             u'Reboccare Olio'],
        12: [u'Filtro Olio', u'Filtro dell’Olio intasato',
             u'Togliere il Filtro e pulirlo con aria compressa'],
        17: [u'Misura Canotto Modificata',
             u'Impostato un valore di misura canotto diversa dalla '
             u'precedentemente trasferita',
             u'Ripetere azzeramento macchina'],
        18: [u'Misura Quota Massima Modificata',
             u'Impostato un valore di lunghezza macchina diverso da quello'
             u' impostato precedentemente',
             u'Trasferire Utensile e ripetere azzeramento macchina'],
        101: [u'Timeout Matrice Avanti',
              u'Mancata verifica sul sensore di matrice avanti',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        102: [u'Timeout Morsa Chiusa',
              u'Mancata verifica sul sensore di morsa chiusa',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        103: [u'Timeout Carro Chiuso',
              u'Mancata verifica sul sensore di carro chiuso',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        104: [u'Timeout Pinza Chiusa',
              u'Mancata verifica sul sensore di pinza chiusa',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        105: [u'Timeout Anima Avanti',
              u'Mancata verifica sul sensore di anima avanti',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        106: [u'Timeout Slitta Avanti',
              u'Mancata verifica sul sensore di slitta avanti',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        107: [u'Timeout Cambio Piano ',
              u'Mancata verifica sul sensore di piano 2',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        114: [u'Timeout Battuta Avanti',
              u'Mancata verifica sul sensore di battuta avanti',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        121: [u'Timeout Matrice Indietro',
              u'Mancata verifica sul sensore di matrice indietro',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        122: [u'Timeout Morsa Aperta',
              u'Mancata verifica sul sensore di morsa aperta',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        123: [u'Timeout Carro Aperto',
              u'Mancata verifica sul sensore di carro aperto',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        124: [u'Timeout Pinza Aperta',
              u'Mancata verifica sul sensore di pinza aperta',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        125: [u'Timeout Anima Indietro',
              u'Mancata verifica sul sensore di anima indietro',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        126: [u'Timeout Slitta Indietro',
              u'Mancata verifica sul sensore di slitta indietro',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        127: [u'Timeout Cambio Piano ',
              u'Mancata verifica sul sensore di piano 1',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        134: [u'Timeout Battuta Indietro',
              u'Mancata verifica sul sensore di battuta avanti',
              u'Verificare la corretta segnalazione del sensore e/o del '
              u'movimento del cilindro'],
        150: [u'Blocco comando Asse-X per INTERFERENZA con Matrice',
              u'Asse R non in posizione corretta',
              u'Selezionare Asse R e portarlo a raggio matrice'],
        151: [u'Blocco inserimento Carro per INTERFERENZA con Asse X',
              u'Asse X in zona di interferenza, non è possibile chiudere '
              u'il carro',
              u'Selezionare Asse X e portalo fuori dalla zona di '
              u'interferenza '],
        152: [u'Blocco discesa piano per INTERFERENZA',
              u'Asse X in zona di interferenza, non è possibile cambiare '
              u'piano',
              u'Selezionare Asse X e portalo fuori dalla zona di '
              u'interferenza'],
        153: [u'Blocco salita piano per INTERFERENZA',
              u'Asse X in zona di interferenza, non è possibile cambiare '
              u'piano',
              u'Selezionare Asse X e portalo fuori dalla zona di '
              u'interferenza'],
        154: [u'Blocco comando Asse-X per strappo tubo. APRIRE '
              u'Morsa/Carro e/o la Pinza',
              u'Non è possibile muovere Asse X per condizioni elencate',
              u'Verificare sensore morsa/carro/pinza aperti o posizionare '
              u'morsa/carro/pinza aperti'],
        155: [u'Blocco comando Asse-Y per strappo tubo. APRIRE Morsa/Carro'
              u' e/o la Pinza',
              u'Non è possibile muovere Asse Y per condizioni elencate',
              u'Verificare sensore morsa/carro/pinza aperti o posizionare '
              u'morsa/carro/pinza aperti'],
        156: [u'Blocco inserimento Carro per INTERFERENZA con Asse R',
              u'Non è possibile chiudere il carro per Asse R non a raggio '
              u'matrice',
              u'Selezionare Asse R e portarlo a raggio matrice'],
        157: [u'Blocco comando Asse-R per carro NON aperto',
              u'Non è possibile muovere Asse R per carro chiuso',
              u'Verificare sensore carro aperto o posizionare carro '
              u'aperto'],
        158: [u'Blocco comando Asse-R Indietro',
              u'Non è possibile muovere Asse R indietro perchè raggiunto '
              u'limite matrice', u''],
        159: [u'Blocco avanti slitta Asse-Y INFERIORE 91°',
              u'Non è possibile muovere slitta avanti perchè in u'
              u'interferenza con asse Y',
              u'Selezionare Asse Y e portarlo a una quota superiore di '
              u'91°'],
        160: [u'Blocco comando Asse-Y per Slitta NON indietro',
              u'Non è possibile muovere Asse Y indietro perchè slitta non '
              u'in posizione indietro',
              u'Verificare sensore slitta indietro o posizionare slitta '
              u'indietro'],
        161: [u'Blocco inserimento Morsa per Asse-Y NON a 0°',
              u'Non è possibile chiudere morsa perchè Asse Y non a zero',
              u'Selezionare Asse Y e portarlo a una quota 0'],
        164: [u'Blocco comando Asse-X per Piano Attuale UGUALE a 0',
              u'Non è possibile muovere Asse X perchè il piano non è '
              u'selezionato',
              u'Verificare sensore piano attuale o cambiare piano 1 – 2'],
        165: [u'Blocco inserimento Morsa per Matrice NON indietro',
              u'Non è possibile chiudere morsa perchè matrice non in '
              u'posizione indietro',
              u'Verificare sensore matrice indietro o posizionare matrice '
              u'indietro'],
        167: [u'Blocco comando inserimento Carro per Slitta NON indietro',
              u'Non è possibile chiudere carro perchè slitta non in '
              u'posizione indietro',
              u'Verificare sensore slitta indietro o posizionare slitta '
              u'indietro'],
        168: [u'Blocco comando Asse-R per morsa NON aperta',
              u'Non è possibile muovere Asse R per morsa chiusa',
              u'Verificare sensore morsa aperta o posizionare morsa '
              u'aperta'],
        169: [u'Blocco Inserimento Morsa INTERFERENZA con Asse R',
              u'Non è possibile chiudere morsa per Asse R non a raggio '
              u'matrice',
              u'Selezionare Asse R e portarlo a raggio matrice'],
        171: [u'Allarme Keyence', u'Modulo di sicurezza Keyence in errore',
              u'Verificare il corretto funzionamento del modulo tramite il'
              u' software installato sul PC'],
        172: [u'ALLARME - Blocco Asse Z per Battuta Giu',
              u'Non è possibile muovere Asse Z per battuta giu',
              u'Verificare sensore battuta su o posizionare battuta su'],
        173: [u'ALLARME - Blocco Battuta per Asse Z > 0',
              u'Non è possibile muovere Battuta per Asse Z non a 0',
              u'Selezionare Asse Z e portarlo a 0'],
    }

    class RobotConnectionError(Exception):
        print(u'Cannot connect with robot')

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
            u'[INFO] Start check alarm robot: %s' % self._robot_name)
        counter = 0
        while True:
            counter += 1

            # Check 200 alarms:
            for alarm in self._alarms.keys():  # range(201):
                if self.get_data_value(
                        'ns=6;s=::AsGlobalPV:Allarmi.N[%s].Dati.Attivo' %
                        alarm):
                    message_data = [self._robot_name]
                    message_data.extend(self._alarms[alarm])
                    event_text = u'[ALARM] Robot: %s\n' \
                                 u'Allarme: %s\n' \
                                 u'Problema: %s\n' \
                                 u'Soluzione: %s' % tuple(message_data)
                    try:
                        bot.sendMessage(self._telegram_group, event_text)
                    except:
                        bot.sendMessage(
                            self._telegram_group, u'Error sending message')

            print(u'Check # %s' % counter)
            time.sleep(seconds)
            if counter % verbose_every == 0:
                bot.sendMessage(
                    self._telegram_group,
                    u'[INFO] Robot %s working check # %s' % (
                        self._robot_name, counter))
            else:
                print(u'Check # %s' % counter)
            """
            # Check master alarm:
            alarm_status = str(self.get_data_value(
                u'ns=6;s=::AsGlobalPV:Allarmi.Presente',
            ))
            if alarm_status:
                event_text = u'Robot: %s Mater Alarm present\n%s' % (
                    self._robot_name,
                    u','.join(alarm_list)
                )
                bot.sendMessage(self._telegram_group, event_text)
            """
            # Check all 200 alarms:
            """
            for alarm in range(201):
                alarm_status = str(self.get_data_value(
                    u'ns=6;s=::AsGlobalPV:Allarmi.N[%s].Dati.Attivo' % alarm,
                ))
                if alarm_status:
                    event_text = u'Robot: %s Alarm present: # %s' % (
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
            # data = u'[ERR] Node access error (not readable!)'
            data = ''  # Error?
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

        # B. Robot:
        self._robot_name = config.get(u'robot', u'name')
        self._robot_address = config.get(u'robot', u'address')
        print(u'Read config file %s for Robot: %s' % (
            self._robot_name,
            self._config_file,
        ))

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
            print(u'Error disconnecting from Robot: %s' % self._name)

    def get_alarm_info(self, number):
        """ Get alarm info by code
        """
        if number in self._alarms:
            return self._alarms[number]
        else:
            return [u'Allarme generico #%s' % number, u'/', u'/']
