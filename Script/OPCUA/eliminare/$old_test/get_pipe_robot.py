#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import pdb
import time
from opcua import Client
from opcua.tools import endpoint_to_strings
# from opcua.common.structures_generator import StructGenerator, _clean_name

uri = "opc.tcp://192.168.1.1:4840"


def get_children(node):
    descs = node.get_children_descriptions()
    descs.sort(key=lambda x: x.BrowseName)
    return descs

def get_endpoints(uri):
    client = Client(uri, timeout=2)
    endpoints = client.connect_and_get_server_endpoints()
    for i, endpoint in enumerate(endpoints, start=1):
        print('[INFO]', 'Endpoint %s:' % i)
        for record in endpoint_to_strings(endpoint):  # name, value
            print('  >>>   %s: %s' % record)
    return endpoints

# endpoints = get_endpoints(uri)

client = Client(uri)
client.connect()
print(client.get_node("ns=6;s=::AsGlobalPV:VersionePLC").get_value())
node = client.get_node("ns=6;s=::AsGlobalPV:OreLavoroUtenza")

"""
for description in node.get_children_descriptions():
    node_desc = client.get_node(description.NodeId)
    print node_desc
"""

client.disconnect()
sys.exit()




root = client.get_root_node()
pdb.set_trace()
# for line in root.get_children():
#     print(line)

# sensor =root.get_child([0])
# descriptions = get_children(root)
# print(descriptions)

sys.exit()
client = Client(uri)
client.connect()
pdb.set_trace()



print("client connect")
root = client.get_root_node()
print("root:", root)
objects = client.get_objects_node()
print(objects)
childnode = objects.get_child("5:Simulation")
print(childnode)
while True:
    counter = client.get_node("ns=5;s=Counter1")
    count = counter.get_value()
    print(count)
    time.sleep(1)

pdb.set_trace()
client.disconnect()
sys.exit()
#temp = client.get_node("ns=2;i=2")

modes = {
    '':  (
    'description',
    'name',
    'nodes',
    'product_uri',
    'max_chunkcount',
    'max_messagesize',
    ),

    '()': (
    'export_xml',
    'find_endpoint',
    'find_servers',
    'find_servers_on_network',
    'get_endpoints',
    'get_namespace_array',
    'get_namespace_index',
    'get_node',
    'get_objects_node',
    'get_root_node',
    'get_server_node',
    'get_values',
    'import_xml',oca
    )
    }

import pdb; pdb.set_trace()
for mode in modes:
    for call in modes[mode]:
        try:
            operation = eval('client.%s%s' % (
                call,
                mode,
                ))
            print('[INFO]', call, '>>>>>', operation)
        except:
            print('[ERROR]', sys.exc_info())

client.disconnect()
sys.exit()
# while True:
#           Temp = client.get_node("ns=2;i=2")
#           Temperature = Temp.get_value()
#           print(Temperature)


# '__class__',
# '__delattr__', '__dict__', '__doc__', '__enter__', '__exit__', '__format__',
# '__getattribute__', '__hash__', '__init__', '__module__', '__new__',
# '__reduce__', '__reduce_ex__',
# '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__',
# '__weakref__', '_add_anonymous_auth', '_add_certificate_auth',
# '_add_user_auth', '_encrypt_password',
# '_password', '_policy_ids', '_server_nonce', '_session_counter',
# '_username',

# 'activate_session', 'application_uri', 'close_secure_channel',
# 'close_session',
# 'connect', 'connect_and_find_servers', 'connect_and_find_servers_on_network',
# 'connect_and_get_server_endpoints', 'connect_socket', 'create_session',
# 'create_subscription', 'delete_nodes',
# 'disconnect', 'disconnect_socket',
# 'keepalive',
# 'load_client_certificate', 'load_enums', 'load_private_key',
# 'open_secure_channel', 'reconciliate_subscription', 'register_namespace',
# 'register_nodes',
# 'secure_channel_id', 'secure_channel_timeout', 'security_policy',
# 'send_hello', 'server_policy_id', 'server_policy_uri', 'server_url',
# 'session_timeout', 'set_password', 'set_security', 'set_security_string',
# 'set_user', 'set_values', 'uaclient', 'unregister_nodes', 'user_certificate',
# 'user_private_key'
# 'load_type_definitions',

