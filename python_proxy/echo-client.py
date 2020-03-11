#!/usr/bin/env python3

import socket
import sys

HOST = '127.0.0.1'  # The server's hostname or IP address

# /* Check command line args */
if len(sys.argv) != 2:
    print("usage: " + sys.argv[0] + " <port>")
    exit()

# make sure given port number is valid
try: 
    PORT = int(sys.argv[1])
except ValueError:
    print("Invalid Port Number")
    exit()


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, PORT))

s.sendall(b'Hello, world')
try:
	while True:
		data = s.recv(1024)
		if not data:
			break
		print(data.decode())
except KeyboardInterrupt:
	print("Interrupted")
	s.close
	exit()
