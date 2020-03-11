 # proxy.py - A program to act as a proxy between a client and a server for HTTP/1.0 Web requests using the GET method.
 # Author - Joshua DeMoss

 #!/usr/bin/env python3

#imports
import sys
import socket
import hashlib
import os

# A buffer size.  Use when buffers have sizes.  Recommended over reading entire
# files or responses into a single bytes object, which may not be particularly
# good when I'm trying to listen to di.fm using the proxy.
BUFSIZ = 4096

# Hard coded variables
user_agent_hdr = b"User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:57.0) Gecko/20100101 Firefox/57.0\r\n"

# Some helper functions

def cachefile(url):
	"""Return a specific filename to use for caching the given URL.

	Please use this to generate cache filenames, passing it the full URL as
	given in the client request.  (This will help me write tests for grading.)
	"""
	return 'cache/' + hashlib.sha256(url).hexdigest()

	# Handles one HTTP request from client, forwards it to the server,
	# gets a response from the server, stores the response in cache,
	# and forwards the response to the client.
def handle(conn):
	# Recieve request and turn it into string
	c_total_data = conn.recv(BUFSIZ)
	c_size = sys.getsizeof(c_total_data)
	while c_size >= BUFSIZ:
		cur_data = conn.recv(BUFSIZ)
		c_total_data += cur_data
		c_size = sys.getsizeof(cur_data)

	c_total_data = c_total_data.split(b'\r\n\r\n')      # Split headers from payload
	c_total_data[0] = c_total_data[0] + b'\r\n\r\n'     # Add carrige return back on 

	c_list_of_lines = c_total_data[0].split(b'\n')      # we send c_total_data[0] along later
	# PARSING AND PREPARING HEADERS TO SEND TO SERVER -----------------------
	
	header_line = c_list_of_lines[0]                  # Retrieve the header line from the c_total_data recieved
	print(header_line)
	header_line_components = header_line.split()    # Split header line into "GET URL HTTP/1.1"

	# # CACHE Fetching:
	# filename = cachefile(header_line_components[1])
	# dirpath = os.getcwd()
	# full_path = dirpath + "/" + filename
	# if os.path.isfile(full_path):
	# 	fileDir = os.path.dirname(os.path.realpath('__file__'))
	# 	filename = os.path.join(fileDir, filename)
	# 	f = open(filename, "rb")
	# 	contents = f.read()
	# 	conn.sendall(contents)
	# 	return


	c_list_of_lines.pop(0)                            # Get rid of the header line from the list

	if (header_line_components[0] != b'GET' and
	 header_line_components[0] != b'CONNECT'):          #Is it a GET request?
		print("\nERROR 501: "+ header_line_components[0].decode() + " requests are Not Implemented")
		print("Proxy does not implement this method\n")
		return

	if header_line_components[1].find(b'http://') != -1:
		url = header_line_components[1][7:]             #Get url without http:// beginning
	else:
		url = header_line_components[1]

	print(url)
	path_start = url.find(b"/")                      # Separate URL from path
	if path_start == -1:
		path = b"/"
	else:
		path = url[path_start:]
		url = url[:path_start]

	colon_location = url.find(b":")                  # Separate URL from port
	if colon_location == -1:
		port = b'80'
	else:
		port = url[colon_location+1:]
		url = url[:colon_location]

	print(url)
													# url, port, and path have been parsed
	header = (b"GET "+path+b" HTTP/1.0\r\n")
	print(header)
	host_hdr = b"Host: " + url + b"\r\n"

	# Check cache for saved responses and send response back to client if available

	# If response is not available then 
	# Open a connection with the end server
	ss = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	ss.connect((url, int(port.decode())))

										# Send Header line and hard coded headers to end server
	ss.sendall(header)
	ss.sendall(host_hdr)
	ss.sendall(user_agent_hdr)
	print(host_hdr)
	print(user_agent_hdr)

	
	 # Forward the rest of the request headers to the End Server
	for line in c_list_of_lines:
		if (line.find(b'Host:') != -1 or line.find(b'User-Agent:') != -1):
			pass
		else:
			line = line + b'\n'
			ss.sendall(line)

	ss.sendall(c_total_data[1])       # send the payload of the request to the end server too
	

	# RESPONSE FROM SERVER ***************************************************************
	s_total_data = ss.recv(BUFSIZ)
	s_size = sys.getsizeof(s_total_data)
	while s_size >= BUFSIZ:
		cur_data = conn.recv(BUFSIZ)
		s_total_data += cur_data
		s_size = sys.getsizeof(cur_data)

	s_total_data = b'HTTP/1.0 ' + s_total_data[9:]
	conn.sendall(s_total_data)
	print(s_total_data)

	if not os.path.exists('cache'):
		os.mkdir('cache')

	filename = cachefile(header_line_components[1])

	fileDir = os.path.dirname(os.path.realpath('__file__'))
	filename = os.path.join(fileDir, filename)

	f = open(filename, "wb")
	f.write(s_total_data)
	f.close()

# MAIN: ***************************************************************************************

# /* Check command line args */
if len(sys.argv) != 2:
	print("usage: " + sys.argv[0] + " <port>")
	exit()

# make sure given port number is valid
try: 
	port = int(sys.argv[1])
except ValueError:
	print("Invalid Port Number")
	exit()

# create a socket, cs
try: 
	cs = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
except socket.error as err: 
	print ("socket creation failed with error " + str(err))

# work around for making sure there is no "socket is use" error
cs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

host = '' # more flexible than hardcoding a host in
cs.bind((host, port))         
try:
	cs.listen()      
except KeyboardInterrupt:
	exit()

# Establish connection w/ client
try:
	while True:   
		conn, addr = cs.accept()      
		print ("Connected to " +  str(addr)) 
		handle(conn)
except KeyboardInterrupt:
	exit()

conn.close()
