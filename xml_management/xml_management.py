#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP)
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import pdb
import logging
from openerp.osv import fields, osv, expression, orm
import xml.etree.cElementTree as ElementTree
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp.tools.translate import _


_logger = logging.getLogger(__name__)


class XmlDictConfig(dict):
    """
    Note: need to add a root into if no existing
    Example usage:
    >> tree = ElementTree.parse('your_file.xml')
    >> root = tree.getroot()
    >> xmldict = XmlDictConfig(root)
    Or, if you want to use an XML string:
    >> root = ElementTree.XML(xml_string)
    >> xmldict = XmlDictConfig(root)
    And then use xmldict for what it is... a dict.
    """
    def __init__(self, parent_element):
        if parent_element.items():
            self.updateShim( dict(parent_element.items()))
        for element in parent_element:
            if len(element):
                aDict = XmlDictConfig(element)
                # if element.items():
                # aDict.updateShim(dict(element.items()))
                self.updateShim({element.tag: aDict})
            elif element.items():    # items() is specially for attributes
                elementattrib = element.items()
                if element.text:
                    elementattrib.append((element.tag, element.text))     # add tag:text if there exist
                self.updateShim({element.tag: dict(elementattrib)})
            else:
                self.updateShim({element.tag: element.text})

    def updateShim (self, aDict):
        for key in aDict.keys():   # keys() includes tag and attributes
            if key in self:
                value = self.pop(key)
                if type(value) is not list:
                    listOfDicts = []
                    listOfDicts.append(value)
                    listOfDicts.append(aDict[key])
                    self.update({key: listOfDicts})
                else:
                    value.append(aDict[key])
                    self.update({key: value})
            else:
                self.update({key: aDict[key]})  # it was self.update(aDict)


class XMLManagement(orm.Model):
    """ Model name: XMLManagement
    """

    _name = 'xml.management'
    _description = 'XML Management'
    _rec_name = 'name'
    _order = 'name'

    # Utility:
    def xml2dict(self, xml_text):
        """ Extract dict with XML text passed
        """
        parent_element = ElementTree.XML(xml_text)
        result_data = XmlDictConfig(parent_element)
        return result_data

    def file2dict(self, filename):
        """ Read all file name and convert to dict
        """
        xml_file = self.open(filename, 'r')
        xml_data = ''
        for line in xml_file:
            xml_data += line.strip()
        return self.xml2dict(xml_data)
