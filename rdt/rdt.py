# !/usr/bin/env python3
# Joshua DeMoss
# Project 2 - RDT
# 3/24/20
# 
# Purpose: Construct a Reliable Data Transfer Protocol from Scratch
# using the given network simulator


from network import Protocol, StreamSocket
import random
from queue import Queue
import time

# Reserved protocol number for experiments; see RFC 3692
IPPROTO_RDT = 0xfe

# This socket class is used in conjuction with the RDTProtocol class below it. 
# The purpose of the socket class is to provide functionality for typical socket functions
# that can opperate with the stop-and-wait protol, reliable data transfer. Main functionality
# of this class lies in the send function, which waits for a ACK message to make sure its sent
# message was recieved, and both the accept anad connect functions which establish connections.
class RDTSocket(StreamSocket):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
       
        # Inherited variables: 
            # data (data)
            # datamu (lock for threading)
            # proto (protocol)

        # Connection Queue
        self.requests = Queue()
        
        # Source Port of this Socket
        self.sPort = None
        
        # Destination Port once connected to another socket
        self.dPort = None
        
        # Destination IP address once " " " "
        self.dIP = None
        
        # Indicates if this socket is currently connected to another socket
        self.connected = False

        # Used to distinguish packets between each other 1 = SYN, 2 = SYN ACK, 3 = ACK, 0 = Regular Message
        self.flag = 0

        # Used to inform the "sending" socket whether it it's sent data was recieved
        self.acked = Falses
    
    # Binds this socket to a port number
    def bind(self, port): # only new definition - the rest are overrides of super class
        
        # will be true if connect() was called or makenewsocket() is called in accept()
        if self.connected: 
            raise StreamSocket.AlreadyConnected

        # Checks to see if port has been used on this socket's host
        elif port in self.proto.usedPorts and self.proto.usedPorts[port][0] == self.proto.host.ip: 
            raise StreamSocket.AddressInUse
    
        self.sPort = port
        self.proto.usedPorts[port] = [self.proto.host.ip, self] # add port to protocol's used ports dictionary

    # Qualifies this socket as a listening socket
    def listen(self):
        if self.sPort == None:
            raise StreamSocket.NotBound
        elif self.connected:
            raise StreamSocket.AlreadyConnected
        
        self.proto.listeningPorts.add(self.sPort)
    
    # Retrieves next request from request queue, makes a new socket, connects the new socket to the requesting socket   
    def accept(self):
        if self.sPort not in self.proto.listeningPorts:
            raise StreamSocket.NotListening
        
        addr = self.requests.get() # get info from request queue
        s = self.proto.makeNewSocket(addr[1], self.sPort, addr[0]) # make a new socket w that info
        
        s.sendACK(2)
        self.proto.connSockets[(addr[1], self.sPort, addr[0])][1] = 1 # set new socket's seq number to 1 (it recieved a 0 in the connect packet)
        return (s, (addr[0], addr[1]))

    # Makes Connection request to destination socket
    def connect(self, addr):
        if self.connected:
            raise StreamSocket.AlreadyConnected
        elif self.sPort in self.proto.listeningPorts:
            raise StreamSocket.AlreadyListening

        self.connected = True
        if self.sPort == None: # Select a random port number for the socket 
            randPort = random.randrange(49152, 65535)
            while randPort in self.proto.usedPorts:
                randPort = random.randrange(49152, 65535)
            self.sPort = randPort
            self.proto.usedPorts[self.sPort] = [self.proto.host.ip, self]

        self.dIP = addr[0]
        self.dPort = addr[1]
        self.sendACK(1) #used to make the initial connection request

    # Used to send data between Sockets
    def send(self, data):
        if not self.connected:
            raise StreamSocket.NotConnected


        # If this packet is a SYN or SYN ACK packet
        if self.flag == 1 or self.flag == 2: 
            seqNum = 0
        
        # else if Packet is an ACK or reg msg
        else: 
            # get the cur seq num of the socket
            seqNum = self.proto.connSockets[(self.dPort, self.sPort, self.dIP)][1] 
        
        # Calculate the checksum and then create the header (20 bytes)
        checksum = self.proto.checksum(self.sPort, self.dPort, seqNum, self.flag, data)   
        hdr = self.proto.packHeader(self.sPort, self.dPort, seqNum, self.flag, checksum) 

        # If packet is a SYN ACK or reg ACK then send it without RDT
        if self.flag == 2 or self.flag == 3: 
            self.output(hdr+data, self.dIP)
        # otherwise provide stop-and-wait RDT
        else:
            # Wait till this socket recieves an ACK before exiting the fun call
            while not self.acked:
                self.output(hdr+data, self.dIP)
                start = time.time()
                while time.time() - start < .01:
                    # The RDT protocl will update this value when it recieves an ACK see input()
                    if self.acked:
                        break
            self.acked = False

        # Sequence numbers are used to gaurd against duplicate messages
        if self.flag != 1: 
            self.proto.connSockets[(self.dPort, self.sPort, self.dIP)][1] = 1 - seqNum

    # Helper function used to reduce code associated with sending an ack
    def sendACK(self, flag):
        self.flag = flag
        self.send(b'')
        self.flag = 0


# ----------------------------------------------------------------------------------------------------------------------------------------------------


# This is a custom RDT protocol. It is stop and wait, meaning each host waits until it recieves
# a rsponse from the device it is communicating with before continuing to send more data. IF the
# host waits more than 10 miliseconds, it resends the message it sent assuming the device it is
# communicating with never recieved its earlier message. The stop and wait functionality is
# implemented in the RDT socket above, specifically in the send function. The main functionality
# of this class is in input which decides what should be done when the host recieves data.
#
# The main functionality provided by this class is in input which parses packets recieved at the
# transport layer, demultiplexes the message based on the custom header, and then performs the appropriate
# actions based on other header information.
class RDTProtocol(Protocol):
    # inherits host from Protocol
    PROTO_ID = IPPROTO_RDT
    SOCKET_CLS = RDTSocket

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Dictionary of all connections on this host
        self.connSockets = {} #(sPort, dPort, sIP)

        # Dictionary of used ports on this host
        self.usedPorts = {}

        # Set of listening ports
        self.listeningPorts = set()

    def input(self, seg, host):
        sPort, dPort, seqNum, flag, checksum, data = self.parseRDT(seg)

        # Check for corruption
        if checksum == self.checksum(sPort, dPort, seqNum, flag, data):
            
            # if its a regular message
            if flag == 0: 
                # Demux by fetching the right socket
                if (sPort, dPort, host) in self.connSockets:
                    correctSocket = self.connSockets[(sPort, dPort, host)][0]
                    if seqNum == self.connSockets[(sPort, dPort, host)][1]:
                        correctSocket.deliver(data)
                        correctSocket.sendACK(3)
                    else:
                        self.connSockets[(sPort, dPort, host)][1] = 1 - self.connSockets[(sPort, dPort, host)][1]
                        correctSocket.sendACK(3)
            
            # If it is a SYN or ACK message
            else: 
                if dPort in self.usedPorts:
                    correctSocket = self.usedPorts[dPort][1]
                    
                    # Setting up a connection
                    if flag == 1: # SYN request
                        if ((host, sPort) not in list(correctSocket.requests.queue)) and ((sPort, dPort, host) not in self.connSockets): #not in queue or connSockets
                            correctSocket.requests.put((host, sPort)) #
                        elif (host, sPort) not in list(correctSocket.requests.queue): #if the connection is already made (queue doesn't contain it though)
                            correctSocket = self.connSockets[(sPort, dPort, host)][0]
                            self.connSockets[(sPort, dPort, host)][1] = 1 - self.connSockets[(sPort, dPort, host)][1] #get the opposite sequence number of that connection
                            correctSocket.sendACK(2) #use that sequence number to send an ACK
                    
                    # Responding to a connection request (aka SYN Request)        
                    elif flag == 2:
                        self.connSockets[(sPort, dPort, host)] = [correctSocket, 1]
                        correctSocket.acked = True # will be set false again by send
                    
                    # Responding to normal messages after connection is already established
                    elif (flag == 3) and ((sPort, dPort, host) in self.connSockets) and (seqNum == self.connSockets[(sPort, dPort, host)][1]):
                        correctSocket = self.connSockets[(sPort, dPort, host)][0]
                        correctSocket.acked = True # Notify the sender that it recieved an ACK by setting acked to true

    # Helper function for accept to make a new socket
    def makeNewSocket(self, sPort, dPort, sIP):
        toReturn = RDTSocket(self)
        toReturn.connected = True
        toReturn.sPort = dPort
        toReturn.dPort = sPort
        toReturn.dIP = sIP
        self.connSockets[(sPort, dPort, sIP)] = [toReturn, 0] #reference to self and sequence number
        return toReturn

    # Helper function to help pack the header bytes
    def packHeader(self, sPort, dPort, seqNum, flag, checksum):
        sPort = sPort.to_bytes(4, 'big')
        dPort = dPort.to_bytes(4, 'big')
        seqNum = seqNum.to_bytes(4, 'big')
        flag = flag.to_bytes(4, 'big')
        checksum = checksum.to_bytes(4, 'big')
        return sPort + dPort + seqNum + flag + checksum

    # Helper function to parse the header bytes
    def parseRDT(self, seg):
        sPort = int.from_bytes(seg[0:4], "big")
        dPort = int.from_bytes(seg[4:8], "big")
        seqNum = int.from_bytes(seg[8:12], "big")
        flag = int.from_bytes(seg[12:16], "big")
        checksum = int.from_bytes(seg[16:20], "big")
        data = seg[20:]
        return sPort, dPort, seqNum, flag, checksum, data

    # Helper function to creat the checksum
    def checksum(self, sPort, dPort, seqNum, flag, data):
        return (sPort + dPort + flag + sum(data)) % ((2 ** 32) - 1)