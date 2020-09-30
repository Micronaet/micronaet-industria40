import socket

hostname = '192.168.1.183'
port = 22

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.connect((hostname, port))
    print("Port 22 reachable")
except socket.error as e:
    print("Error on connect: %s" % e)
sock.close()
